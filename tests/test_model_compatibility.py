"""Verify model parameters at the commit-generation API boundary."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from openai import AsyncOpenAI

from git_ai_commit import GitAICommit
from model_compatibility import model_parameters


def make_committer(model: str, effort: object, mode: str = "generation") -> GitAICommit:
    committer = GitAICommit.__new__(GitAICommit)
    committer.config = {
        "openai": {
            "model": model,
            "reasoning_effort": effort,
            "temperature": 0.7,
            "max_tokens": 2000,
        },
    }
    committer.mode = mode
    committer.partial_text = "fix: " if mode == "completion" else ""
    committer.get_staged_changes = Mock(return_value="diff --git a/app.py b/app.py")
    committer._build_system_prompt = Mock(return_value="Generate a commit message.")
    committer._build_user_prompt = Mock(return_value="Staged diff")
    committer._build_completion_prompt = Mock(return_value=("Continue.", "fix: "))
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="fix: handle input"))],
    )
    committer.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=response)),
        ),
    )
    return committer


@pytest.mark.parametrize("mode", ["generation", "completion"])
@pytest.mark.parametrize(
    "model,configured,effective,temperature",
    [
        ("gpt-6-luna", "none", "none", True),
        ("gpt-6-luna", "low", "low", False),
        ("gpt-6-luna", "minimal", "low", False),
        ("gpt-6-luna", "max", "max", False),
        ("gpt-6-sol", "none", "none", True),
        ("gpt-6.1-sol", "none", "low", False),
        ("gpt-6-astra", "none", "low", False),
        ("gpt-6-astra", "minimal", "low", False),
        ("gpt-6-astra", "max", "max", False),
        ("gpt-5", "none", "minimal", False),
        ("gpt-5-mini", "none", "minimal", False),
        ("gpt-5-nano-2025-08-07", "none", "minimal", False),
        ("gpt-5", "xhigh", "high", False),
        ("gpt-5.1", "minimal", "low", False),
        ("gpt-5.1", "none", "none", True),
        ("gpt-5.1", "max", "high", False),
        ("gpt-5.2", "max", "xhigh", False),
        ("gpt-5.2", "none", "none", True),
        ("gpt-5.4-mini", "none", "none", True),
        ("gpt-5.4-mini-2026-03-17", "max", "xhigh", False),
        ("gpt-5.4", "low", "low", False),
        ("gpt-5.5", "max", "xhigh", False),
        ("gpt-5.6-luna", "max", "max", False),
        ("gpt-6-luna", None, None, False),
        ("gpt-6-astra", None, None, False),
        ("gpt-4.1", "none", None, True),
        ("o3-mini", "none", "low", False),
    ],
)
async def test_model_parameters(
    model, configured, effective, temperature, mode
) -> None:
    committer = make_committer(model, configured, mode)

    suggestion = await committer.generate_suggestion()

    assert suggestion == (
        "handle input" if mode == "completion" else "fix: handle input"
    )
    params = committer.client.chat.completions.create.call_args.kwargs
    assert params["model"] == model
    assert params.get("reasoning_effort") == effective
    assert ("temperature" in params) is temperature
    if temperature:
        assert params["temperature"] == 0.7
    assert params["max_completion_tokens"] == 2000
    assert "max_tokens" not in params
    assert params["messages"][0]["role"] == "system"


@pytest.mark.parametrize("effort", ["urgent", 3, True])
async def test_invalid_effort_fails_before_api_call(effort, capsys) -> None:
    committer = make_committer("gpt-6-luna", effort)

    assert await committer.generate_suggestion() is None
    committer.client.chat.completions.create.assert_not_awaited()
    assert "reasoning_effort" in capsys.readouterr().err


@pytest.mark.parametrize(
    "model",
    [
        "gpt-6-unknown",
        "gpt-5.4-pro",
        "gpt-5.3-codex",
        "gpt-5-chat-latest",
        "gpt-5.1-chat-latest",
        "o5-mini",
        "gpt-7",
        "custom-model",
    ],
)
async def test_unknown_models_use_conservative_parameters(model) -> None:
    committer = make_committer(model, "none")

    assert await committer.generate_suggestion() == "fix: handle input"
    params = committer.client.chat.completions.create.call_args.kwargs
    assert params["model"] == model
    assert "reasoning_effort" not in params
    assert "temperature" not in params


@pytest.mark.parametrize("effort", [None, "", False, "  "])
@pytest.mark.parametrize(
    "model", ["gpt-5", "gpt-6-luna", "gpt-6-astra", "o3-mini", "o1-mini"]
)
async def test_disabled_effort_is_omitted(model, effort) -> None:
    committer = make_committer(model, effort)

    assert await committer.generate_suggestion() == "fix: handle input"
    params = committer.client.chat.completions.create.call_args.kwargs
    assert "reasoning_effort" not in params
    assert "temperature" not in params


def test_missing_effort_is_omitted() -> None:
    assert model_parameters({"model": "gpt-6-luna"}) == {"model": "gpt-6-luna"}


@pytest.mark.parametrize("effort", ["low", "none"])
def test_o1_mini_never_receives_effort(effort) -> None:
    assert model_parameters({"model": "o1-mini", "reasoning_effort": effort}) == {
        "model": "o1-mini"
    }


@pytest.mark.parametrize("max_tokens", [0, None, "", False])
async def test_unlimited_output_omits_token_limit(max_tokens) -> None:
    committer = make_committer("gpt-6-luna", "none")
    committer.config["openai"]["max_tokens"] = max_tokens

    await committer.generate_suggestion()

    assert (
        "max_completion_tokens"
        not in committer.client.chat.completions.create.call_args.kwargs
    )


@pytest.mark.parametrize(
    "model,effort", [("gpt-6-luna", "none"), ("gpt-6-astra", "low")]
)
async def test_real_sdk_serializes_compatible_request(model, effort) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "fix: handle input",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    committer = make_committer(model, "none")
    async with AsyncOpenAI(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as client:
        committer.client = client

        assert await committer.generate_suggestion() == "fix: handle input"

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/chat/completions"
    body = json.loads(requests[0].content)
    assert body["model"] == model
    assert body["reasoning_effort"] == effort
    assert ("temperature" in body) is (effort == "none")
    assert body["max_completion_tokens"] == 2000


def test_config_precedence_keeps_effort_compatible(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / ".config" / "git-ai-commit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "openai:\n  model: gpt-6-luna\n  reasoning_effort: none\n",
    )
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git-ai-commit.yaml").write_text("openai:\n  model: gpt-5-nano\n")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    committer = GitAICommit.__new__(GitAICommit)
    committer._get_repo_path = Mock(return_value=repo_dir)

    config = committer._load_config()

    assert config["openai"]["model"] == "gpt-5-nano"
    assert config["openai"]["reasoning_effort"] == "none"
    params = model_parameters(config["openai"])
    assert params["reasoning_effort"] == "minimal"
    assert "temperature" not in params
