"""Tests for generation and completion modes."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestModeDetection:
    """Tests for mode detection from environment variables."""

    def test_default_mode_is_generation(self, mock_git_repo: Path):
        """Default mode is generation when env var not set."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            # Ensure mode env vars are not set
            os.environ.pop("GIT_AI_COMMIT_MODE", None)
            os.environ.pop("GIT_AI_COMMIT_PARTIAL_TEXT", None)

            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                assert instance.mode == "generation"
                assert instance.partial_text == ""
            finally:
                os.chdir(original_dir)

    def test_generation_mode_from_env(self, mock_git_repo: Path):
        """Generation mode is detected from environment variable."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "GIT_AI_COMMIT_MODE": "generation",
        }):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                assert instance.mode == "generation"
            finally:
                os.chdir(original_dir)

    def test_completion_mode_from_env(self, mock_git_repo: Path):
        """Completion mode is detected from environment variable."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "GIT_AI_COMMIT_MODE": "completion",
            "GIT_AI_COMMIT_PARTIAL_TEXT": "feat: add",
        }):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                assert instance.mode == "completion"
                assert instance.partial_text == "feat: add"
            finally:
                os.chdir(original_dir)


class TestGenerationMode:
    """Tests for generation mode functionality."""

    @pytest.mark.asyncio
    async def test_generation_mode_builds_correct_prompts(self, mock_git_repo_with_changes: Path):
        """Generation mode builds system and user prompts correctly."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "GIT_AI_COMMIT_MODE": "generation",
        }):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()

                # Mock the API call
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: add hello function"

                async def mock_create(**kwargs):
                    return mock_response

                instance.client.chat.completions.create = mock_create

                result = await instance.generate_suggestion()

                assert result == "feat: add hello function"
            finally:
                os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_generation_mode_no_staged_changes(self, mock_git_repo: Path, capsys):
        """Generation mode handles no staged changes."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                result = await instance.generate_suggestion()

                assert result is None
                captured = capsys.readouterr()
                assert "No staged changes" in captured.err
            finally:
                os.chdir(original_dir)


class TestCompletionMode:
    """Tests for completion mode functionality."""

    @pytest.mark.asyncio
    async def test_completion_mode_builds_completion_prompts(self, mock_git_repo_with_changes: Path):
        """Completion mode builds completion-specific prompts."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "GIT_AI_COMMIT_MODE": "completion",
            "GIT_AI_COMMIT_PARTIAL_TEXT": "feat: add",
        }):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()

                # Mock the API call
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = " user authentication"

                async def mock_create(**kwargs):
                    # Verify completion-specific prompts are used
                    messages = kwargs.get("messages", [])
                    system_msg = messages[0]["content"]
                    assert "completion" in system_msg.lower()
                    return mock_response

                instance.client.chat.completions.create = mock_create

                result = await instance.generate_suggestion()

                assert result == " user authentication"
            finally:
                os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_completion_strips_repeated_partial(self, mock_git_repo_with_changes: Path):
        """Completion mode strips partial text if AI repeats it."""
        from git_ai_commit import GitAICommit

        partial_text = "feat: add"

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "GIT_AI_COMMIT_MODE": "completion",
            "GIT_AI_COMMIT_PARTIAL_TEXT": partial_text,
        }):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()

                # Mock API returning full message (AI mistake)
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: add user auth"

                async def mock_create(**kwargs):
                    return mock_response

                instance.client.chat.completions.create = mock_create

                result = await instance.generate_suggestion()

                # Should strip the partial text
                assert result == " user auth"
            finally:
                os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_completion_strips_trimmed_partial(self, mock_git_repo_with_changes: Path):
        """Completion mode strips partial text even if AI trimmed whitespace."""
        from git_ai_commit import GitAICommit

        partial_text = "feat: add "  # Note trailing space

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "GIT_AI_COMMIT_MODE": "completion",
            "GIT_AI_COMMIT_PARTIAL_TEXT": partial_text,
        }):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()

                # Mock API returning message starting with trimmed partial
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: adduser auth"  # AI trimmed space

                async def mock_create(**kwargs):
                    return mock_response

                instance.client.chat.completions.create = mock_create

                result = await instance.generate_suggestion()

                # Should strip the trimmed partial
                assert result == "user auth"
            finally:
                os.chdir(original_dir)


class TestModelParameters:
    """Tests for model-specific API parameters."""

    @pytest.mark.asyncio
    async def test_temperature_set_for_gpt4(self, mock_git_repo_with_changes: Path):
        """Temperature is set for GPT-4 models."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                instance.config["openai"]["model"] = "gpt-4"

                captured_params = {}

                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: test"

                async def mock_create(**kwargs):
                    captured_params.update(kwargs)
                    return mock_response

                instance.client.chat.completions.create = mock_create
                await instance.generate_suggestion()

                assert "temperature" in captured_params
            finally:
                os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_no_temperature_for_gpt5(self, mock_git_repo_with_changes: Path):
        """Temperature is not set for GPT-5 models."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                instance.config["openai"]["model"] = "gpt-5-nano"

                captured_params = {}

                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: test"

                async def mock_create(**kwargs):
                    captured_params.update(kwargs)
                    return mock_response

                instance.client.chat.completions.create = mock_create
                await instance.generate_suggestion()

                assert "temperature" not in captured_params
            finally:
                os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_no_temperature_for_reasoning_models(self, mock_git_repo_with_changes: Path):
        """Temperature is not set for reasoning models (o1, o3, o4)."""
        from git_ai_commit import GitAICommit

        for model in ["o1-mini", "o3-mini", "o4-mini"]:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                original_dir = os.getcwd()
                os.chdir(mock_git_repo_with_changes)
                try:
                    instance = GitAICommit()
                    instance.config["openai"]["model"] = model

                    captured_params = {}

                    mock_response = MagicMock()
                    mock_response.choices = [MagicMock()]
                    mock_response.choices[0].message.content = "feat: test"

                    async def mock_create(**kwargs):
                        captured_params.update(kwargs)
                        return mock_response

                    instance.client.chat.completions.create = mock_create
                    await instance.generate_suggestion()

                    assert "temperature" not in captured_params, f"Temperature should not be set for {model}"
                finally:
                    os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_reasoning_effort_for_reasoning_models(self, mock_git_repo_with_changes: Path):
        """Reasoning effort is set for reasoning models."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                instance.config["openai"]["model"] = "o4-mini"
                instance.config["openai"]["reasoning_effort"] = "medium"

                captured_params = {}

                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: test"

                async def mock_create(**kwargs):
                    captured_params.update(kwargs)
                    return mock_response

                instance.client.chat.completions.create = mock_create
                await instance.generate_suggestion()

                assert captured_params.get("reasoning_effort") == "medium"
            finally:
                os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_max_tokens_not_set_when_zero(self, mock_git_repo_with_changes: Path):
        """Max tokens is not set when configured as 0."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                instance.config["openai"]["max_tokens"] = 0

                captured_params = {}

                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: test"

                async def mock_create(**kwargs):
                    captured_params.update(kwargs)
                    return mock_response

                instance.client.chat.completions.create = mock_create
                await instance.generate_suggestion()

                assert "max_completion_tokens" not in captured_params
            finally:
                os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_max_tokens_set_when_positive(self, mock_git_repo_with_changes: Path):
        """Max tokens is set when configured as positive value."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                instance.config["openai"]["max_tokens"] = 1000

                captured_params = {}

                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "feat: test"

                async def mock_create(**kwargs):
                    captured_params.update(kwargs)
                    return mock_response

                instance.client.chat.completions.create = mock_create
                await instance.generate_suggestion()

                assert captured_params.get("max_completion_tokens") == 1000
            finally:
                os.chdir(original_dir)


class TestErrorHandling:
    """Tests for error handling in generate_suggestion."""

    def test_missing_api_key_raises(self, mock_git_repo: Path):
        """Missing API key raises ValueError."""
        from git_ai_commit import GitAICommit

        # Remove API key from environment
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)

        original_dir = os.getcwd()
        os.chdir(mock_git_repo)
        try:
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                    GitAICommit()
        finally:
            os.chdir(original_dir)

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self, mock_git_repo_with_changes: Path, capsys):
        """API errors are caught and return None."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()

                async def mock_create(**kwargs):
                    raise Exception("API Error")

                instance.client.chat.completions.create = mock_create

                result = await instance.generate_suggestion()

                assert result is None
                captured = capsys.readouterr()
                assert "Error" in captured.err
            finally:
                os.chdir(original_dir)
