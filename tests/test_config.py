"""Tests for configuration loading and merging."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_default_config_loads(self):
        """Default configuration file exists and loads correctly."""
        config_path = Path(__file__).parent.parent / "config" / "default_config.yaml"
        assert config_path.exists()

        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "suggestion" in config
        assert "openai" in config
        assert "context" in config
        assert "convention_configs" in config

    def test_default_config_has_required_keys(self):
        """Default configuration has all required keys."""
        config_path = Path(__file__).parent.parent / "config" / "default_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Check suggestion settings
        assert "convention" in config["suggestion"]
        assert "format" in config["suggestion"]
        assert "max_length_per_line" in config["suggestion"]

        # Check openai settings
        assert "model" in config["openai"]

        # Check convention configs
        assert "conventional" in config["convention_configs"]
        assert "gitmoji" in config["convention_configs"]
        assert "traditional" in config["convention_configs"]


class TestConfigMerging:
    """Tests for configuration merging logic."""

    def test_merge_flat_values(self, sample_config):
        """Flat values are properly overridden."""
        # Import here to avoid import issues
        from git_ai_commit import GitAICommit

        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        # Create a mock instance to access _merge_config
        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._merge_config(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_nested_values(self, sample_config):
        """Nested values are properly merged."""
        from git_ai_commit import GitAICommit

        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 3, "c": 4}}

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._merge_config(base, override)

        assert result == {"outer": {"a": 1, "b": 3, "c": 4}}

    def test_merge_deep_nested(self, sample_config):
        """Deep nested structures are properly merged."""
        from git_ai_commit import GitAICommit

        base = {"l1": {"l2": {"l3": {"a": 1, "b": 2}}}}
        override = {"l1": {"l2": {"l3": {"b": 3}}}}

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._merge_config(base, override)

        assert result == {"l1": {"l2": {"l3": {"a": 1, "b": 3}}}}

    def test_override_replaces_non_dict(self, sample_config):
        """Non-dict values are completely replaced."""
        from git_ai_commit import GitAICommit

        base = {"key": [1, 2, 3]}
        override = {"key": [4, 5]}

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._merge_config(base, override)

        assert result == {"key": [4, 5]}


class TestConfigFileLoading:
    """Tests for loading config files."""

    def test_load_yaml_config(self, temp_dir: Path):
        """YAML config files are loaded correctly."""
        from git_ai_commit import GitAICommit

        config_file = temp_dir / "config.yaml"
        config_data = {"suggestion": {"convention": "gitmoji"}}
        config_file.write_text(yaml.dump(config_data))

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._load_config_file(config_file)

        assert result == config_data

    def test_load_yml_config(self, temp_dir: Path):
        """YML config files are loaded correctly."""
        from git_ai_commit import GitAICommit

        config_file = temp_dir / "config.yml"
        config_data = {"openai": {"model": "gpt-4"}}
        config_file.write_text(yaml.dump(config_data))

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._load_config_file(config_file)

        assert result == config_data

    def test_load_json_config_with_deprecation_warning(self, temp_dir: Path, capsys):
        """JSON config files load with deprecation warning."""
        from git_ai_commit import GitAICommit

        config_file = temp_dir / "config.json"
        config_data = {"suggestion": {"convention": "traditional"}}
        config_file.write_text(json.dumps(config_data))

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._load_config_file(config_file)

        assert result == config_data
        # Warning should be printed (to stderr via print_output)
        captured = capsys.readouterr()
        assert "deprecated" in captured.err.lower() or "deprecated" in captured.out.lower()

    def test_invalid_yaml_returns_empty_dict(self, temp_dir: Path):
        """Invalid YAML files return empty dict."""
        from git_ai_commit import GitAICommit

        config_file = temp_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._load_config_file(config_file)

        assert result == {}

    def test_empty_yaml_returns_empty_dict(self, temp_dir: Path):
        """Empty YAML files return empty dict."""
        from git_ai_commit import GitAICommit

        config_file = temp_dir / "config.yaml"
        config_file.write_text("")

        with patch.object(GitAICommit, "__init__", lambda x: None):
            instance = GitAICommit()
            result = instance._load_config_file(config_file)

        assert result == {}


class TestConfigPrecedence:
    """Tests for configuration precedence."""

    def test_project_config_overrides_global(self, mock_git_repo: Path, temp_dir: Path):
        """Project config overrides global config."""
        from git_ai_commit import GitAICommit

        # Set up global config
        global_config_dir = temp_dir / ".config" / "git-ai-commit"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config.yaml"
        global_config.write_text(yaml.dump({"suggestion": {"convention": "traditional"}}))

        # Set up project config
        project_config = mock_git_repo / ".git-ai-commit.yaml"
        project_config.write_text(yaml.dump({"suggestion": {"convention": "gitmoji"}}))

        # Mock the environment
        with patch.object(Path, "home", return_value=temp_dir):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                # Change to the git repo directory
                original_dir = os.getcwd()
                os.chdir(mock_git_repo)
                try:
                    instance = GitAICommit()
                    assert instance.config["suggestion"]["convention"] == "gitmoji"
                finally:
                    os.chdir(original_dir)

    def test_yaml_takes_precedence_over_json(self, mock_git_repo: Path, temp_dir: Path):
        """YAML config takes precedence over JSON when both exist."""
        from git_ai_commit import GitAICommit

        # Create both configs
        yaml_config = mock_git_repo / ".git-ai-commit.yaml"
        yaml_config.write_text(yaml.dump({"suggestion": {"convention": "gitmoji"}}))

        json_config = mock_git_repo / ".git-ai-commit.json"
        json_config.write_text(json.dumps({"suggestion": {"convention": "traditional"}}))

        with patch.object(Path, "home", return_value=temp_dir):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                original_dir = os.getcwd()
                os.chdir(mock_git_repo)
                try:
                    instance = GitAICommit()
                    # YAML should take precedence
                    assert instance.config["suggestion"]["convention"] == "gitmoji"
                finally:
                    os.chdir(original_dir)


class TestConventionConfigs:
    """Tests for convention configuration access."""

    def test_conventional_config_exists(self):
        """Conventional commit config is accessible."""
        config_path = Path(__file__).parent.parent / "config" / "default_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        conv = config["convention_configs"]["conventional"]
        assert "types" in conv
        assert "feat" in conv["types"]
        assert "fix" in conv["types"]

    def test_gitmoji_config_exists(self):
        """Gitmoji config is accessible."""
        config_path = Path(__file__).parent.parent / "config" / "default_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        gitmoji = config["convention_configs"]["gitmoji"]
        assert "prefixes" in gitmoji

    def test_traditional_config_exists(self):
        """Traditional config is accessible."""
        config_path = Path(__file__).parent.parent / "config" / "default_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        trad = config["convention_configs"]["traditional"]
        assert "single-line" in trad or "multi-line" in trad
