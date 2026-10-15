"""Verify backend configuration, selection and the API backend."""

import json
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from conftest import make_repo, wait_for_record, wait_until_dead
from git_ai_commit import DEFAULT_CONFIG, GitAICommit, main
from git_ai_commit_backends import (
    ApiBackend,
    CommandBackend,
    build_backend,
    normalize_legacy_config,
    resolve_backend,
)

SCRIPT = Path(__file__).parents[1] / "src" / "git_ai_commit.py"


def load_config(tmp_path: Path, monkeypatch, global_yaml: str, project_yaml: str):
    config_dir = tmp_path / ".config" / "git-ai-commit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(global_yaml)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git-ai-commit.yaml").write_text(project_yaml)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    committer = GitAICommit.__new__(GitAICommit)
    committer._get_repo_path = Mock(return_value=repo_dir)
    return committer._load_config()


def test_default_config_uses_api_block() -> None:
    assert "openai" not in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["api"]["provider"] == "openai"
    assert DEFAULT_CONFIG["api"]["model"] == "gpt-6-luna"


def test_legacy_openai_block_moves_under_api() -> None:
    assert normalize_legacy_config({"openai": {"model": "gpt-5-nano"}}) == {
        "api": {"provider": "openai", "model": "gpt-5-nano"}
    }


def test_api_keys_win_over_legacy_keys_in_same_file() -> None:
    config = {
        "openai": {"model": "gpt-5-nano", "temperature": 0.2},
        "api": {"model": "gpt-6-luna"},
    }

    assert normalize_legacy_config(config) == {
        "api": {"provider": "openai", "model": "gpt-6-luna", "temperature": 0.2}
    }


def test_config_without_legacy_block_is_unchanged() -> None:
    config = {"api": {"model": "gpt-6-luna"}}

    assert normalize_legacy_config(config) is config


def test_non_mapping_config_is_passed_through() -> None:
    assert normalize_legacy_config(["not", "a", "mapping"]) == ["not", "a", "mapping"]


def test_legacy_global_and_new_project_config_merge(tmp_path, monkeypatch) -> None:
    config = load_config(
        tmp_path,
        monkeypatch,
        global_yaml="openai:\n  model: gpt-6-luna\n  reasoning_effort: low\n",
        project_yaml="api:\n  model: gpt-5-nano\n",
    )

    assert "openai" not in config
    assert config["api"]["provider"] == "openai"
    assert config["api"]["model"] == "gpt-5-nano"
    assert config["api"]["reasoning_effort"] == "low"


@pytest.fixture(autouse=True)
def no_backend_env(monkeypatch) -> None:
    monkeypatch.delenv("GIT_AI_COMMIT_BACKEND", raising=False)


@pytest.mark.parametrize(
    "override,env,configured,expected",
    [
        ("command", "api", "api", "command"),
        (None, "command", "api", "command"),
        (None, None, "command", "command"),
        (None, None, None, "api"),
        (None, " Command ", None, "command"),
    ],
)
def test_backend_precedence(override, env, configured, expected, monkeypatch) -> None:
    if env is not None:
        monkeypatch.setenv("GIT_AI_COMMIT_BACKEND", env)
    config = {} if configured is None else {"backend": configured}

    assert resolve_backend(config, override) == expected


def test_unknown_backend_lists_valid_names() -> None:
    with pytest.raises(
        ValueError, match="Unknown backend 'nope'. Use one of: api, command"
    ):
        resolve_backend({"backend": "nope"})


def test_api_backend_requires_key_only_when_used(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(
        ValueError, match="OPENAI_API_KEY environment variable is not set"
    ):
        build_backend({"api": {"provider": "openai", "model": "gpt-6-luna"}}, "api")
    assert isinstance(
        build_backend({"command": {"argv": ["claude", "-p"]}}, "command"),
        CommandBackend,
    )


def test_unsupported_api_provider_has_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(
        ValueError, match="Unsupported api.provider 'gemini'. Supported: openai"
    ):
        ApiBackend({"provider": "gemini", "model": "x"})


def test_command_config_merges_across_files(tmp_path, monkeypatch) -> None:
    config = load_config(
        tmp_path,
        monkeypatch,
        global_yaml="command:\n  timeout_seconds: 15\n",
        project_yaml="backend: command\ncommand:\n  argv: [claude, -p]\n",
    )

    command = build_backend(config, resolve_backend(config))
    assert command == CommandBackend(argv=("claude", "-p"), timeout_seconds=15)


def test_main_generates_with_command_backend(
    fake_cli, tmp_path, monkeypatch, capsys
) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text(
        "backend: command\ncommand:\n  argv: [fake-cli]\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("FAKE_REPLY", "```\nfeat: add app\n```")
    monkeypatch.chdir(repo)

    assert main([]) == 0

    assert capsys.readouterr().out.strip() == "feat: add app"
    assert "diff --git a/app.py b/app.py" in json.loads(fake_cli.read_text())["stdin"]


def test_backend_flag_overrides_config(fake_cli, tmp_path, monkeypatch, capsys) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text("command:\n  argv: [fake-cli]\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(repo)

    assert main(["--backend", "command"]) == 0
    assert capsys.readouterr().out.strip() == "feat: add thing"


def test_command_errors_are_reported(tmp_path, monkeypatch, capsys) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text(
        "backend: command\ncommand:\n  argv: [nope-cli]\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(repo)

    assert main([]) == 1
    assert "Error: command 'nope-cli' not found on PATH" in capsys.readouterr().err


def test_invalid_backend_flag_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["--backend", "nope"])


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
async def test_interrupting_generation_kills_command(
    signum, fake_cli, tmp_path, monkeypatch
) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text(
        "backend: command\ncommand:\n  argv: [fake-cli]\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKE_SLEEP", "30")
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    record = await wait_for_record(fake_cli)

    process.send_signal(signum)
    process.wait(timeout=10)

    await wait_until_dead(record["pid"])
    assert process.returncode != 0
