"""Verify backend configuration, selection and the API backend."""

from pathlib import Path
from unittest.mock import Mock

from git_ai_commit_backends import normalize_legacy_config

from git_ai_commit import DEFAULT_CONFIG, GitAICommit


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
