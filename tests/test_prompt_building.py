"""Tests for prompt building functionality."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestStaticContext:
    """Tests for static context building."""

    def test_static_context_includes_repo_name(self, mock_git_repo: Path):
        """Static context includes repository name."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                context = instance._build_static_context()

                assert f"Repository: {mock_git_repo.name}" in context
            finally:
                os.chdir(original_dir)

    def test_static_context_includes_branch(self, mock_git_repo: Path):
        """Static context includes branch information."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                context = instance._build_static_context()

                assert "Branch:" in context
            finally:
                os.chdir(original_dir)

    def test_static_context_includes_author(self, mock_git_repo: Path):
        """Static context includes author information."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                context = instance._build_static_context()

                assert "Author: Test User" in context
            finally:
                os.chdir(original_dir)


class TestDynamicContext:
    """Tests for dynamic context building."""

    def test_dynamic_context_includes_change_summary(self, mock_git_repo_with_changes: Path, sample_diff):
        """Dynamic context includes change summary."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                context = instance._build_dynamic_context(sample_diff)

                assert "Change Summary" in context
                assert "Files modified:" in context
                assert "Lines added:" in context
            finally:
                os.chdir(original_dir)

    def test_dynamic_context_includes_diff(self, mock_git_repo_with_changes: Path, sample_diff):
        """Dynamic context includes the staged diff."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                context = instance._build_dynamic_context(sample_diff)

                assert "Staged Changes" in context
                assert "def hello" in context
            finally:
                os.chdir(original_dir)

    def test_dynamic_context_marks_test_changes(self, mock_git_repo_with_changes: Path, sample_diff_with_tests):
        """Dynamic context marks when tests are changed."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                context = instance._build_dynamic_context(sample_diff_with_tests)

                assert "test changes: Yes" in context
            finally:
                os.chdir(original_dir)


class TestSystemPrompt:
    """Tests for system prompt building."""

    def test_system_prompt_includes_convention(self, mock_git_repo: Path):
        """System prompt includes the convention guide."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                prompt = instance._build_system_prompt()

                assert "conventional" in prompt.lower()
                assert "Convention Guide" in prompt
            finally:
                os.chdir(original_dir)

    def test_system_prompt_includes_format_requirements(self, mock_git_repo: Path):
        """System prompt includes format requirements."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                prompt = instance._build_system_prompt()

                # Should include max line length guidance
                assert "72" in prompt or "characters" in prompt
            finally:
                os.chdir(original_dir)

    def test_system_prompt_forbids_markdown(self, mock_git_repo: Path):
        """System prompt forbids markdown formatting."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                prompt = instance._build_system_prompt()

                assert "Do NOT use" in prompt
                assert "markdown" in prompt.lower()
            finally:
                os.chdir(original_dir)


class TestUserPrompt:
    """Tests for user prompt building."""

    def test_user_prompt_includes_dynamic_context(self, mock_git_repo_with_changes: Path, sample_diff):
        """User prompt includes dynamic context."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                prompt = instance._build_user_prompt(sample_diff)

                assert "Generate a commit message" in prompt
                assert "def hello" in prompt
            finally:
                os.chdir(original_dir)

    def test_user_prompt_ends_with_instruction(self, mock_git_repo_with_changes: Path, sample_diff):
        """User prompt ends with clear instruction."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                prompt = instance._build_user_prompt(sample_diff)

                assert "Generate only the commit message" in prompt
            finally:
                os.chdir(original_dir)


class TestCompletionPrompt:
    """Tests for completion mode prompt building."""

    def test_completion_prompt_system_message(self, mock_git_repo_with_changes: Path, sample_diff):
        """Completion prompt system message has correct instructions."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                system, user = instance._build_completion_prompt(sample_diff, "feat: add")

                assert "completion assistant" in system.lower()
                assert "Match the user's style EXACTLY" in system
                assert "ONLY the continuation" in system
            finally:
                os.chdir(original_dir)

    def test_completion_prompt_includes_partial_text(self, mock_git_repo_with_changes: Path, sample_diff):
        """Completion prompt includes the partial text."""
        from git_ai_commit import GitAICommit

        partial = "feat(auth): implement user"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                system, user = instance._build_completion_prompt(sample_diff, partial)

                assert partial in user
                assert "PARTIAL MESSAGE" in user
            finally:
                os.chdir(original_dir)

    def test_completion_prompt_empty_partial(self, mock_git_repo_with_changes: Path, sample_diff):
        """Completion prompt handles empty partial text."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                system, user = instance._build_completion_prompt(sample_diff, "")

                assert "empty - user just opened quote" in user
            finally:
                os.chdir(original_dir)

    def test_completion_prompt_spacing_hint(self, mock_git_repo_with_changes: Path, sample_diff):
        """Completion prompt adds spacing hint when needed."""
        from git_ai_commit import GitAICommit

        # Partial text without trailing space or punctuation
        partial = "feat: add login"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                system, user = instance._build_completion_prompt(sample_diff, partial)

                assert "space" in user.lower()
            finally:
                os.chdir(original_dir)

    def test_completion_prompt_line_length_awareness(self, mock_git_repo_with_changes: Path, sample_diff):
        """Completion prompt is aware of remaining line length."""
        from git_ai_commit import GitAICommit

        partial = "feat: this is a longer partial message that takes"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo_with_changes)
            try:
                instance = GitAICommit()
                system, user = instance._build_completion_prompt(sample_diff, partial)

                # Should mention remaining characters
                assert "characters" in system.lower()
                assert "remaining" in system.lower()
            finally:
                os.chdir(original_dir)


class TestConventionGuide:
    """Tests for convention guide generation."""

    def test_conventional_guide(self, mock_git_repo: Path):
        """Conventional commit guide is generated correctly."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                guide = instance._get_convention_guide("conventional")

                assert "feat" in guide
                assert "fix" in guide
            finally:
                os.chdir(original_dir)

    def test_gitmoji_guide(self, mock_git_repo: Path):
        """Gitmoji guide is generated correctly."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                guide = instance._get_convention_guide("gitmoji")

                # Gitmoji uses prefixes
                assert "prefix" in guide.lower() or "feat" in guide
            finally:
                os.chdir(original_dir)

    def test_invalid_convention_raises(self, mock_git_repo: Path):
        """Invalid convention name raises ValueError."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()

                with pytest.raises(ValueError, match="does not exist"):
                    instance._get_convention_guide("nonexistent")
            finally:
                os.chdir(original_dir)


class TestTokenBudgeting:
    """Tests for token budget management."""

    def test_estimate_tokens(self, mock_git_repo: Path):
        """Token estimation works correctly."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()

                # ~4 chars per token
                text = "a" * 400
                tokens = instance._estimate_tokens(text)

                assert tokens == 100
            finally:
                os.chdir(original_dir)

    def test_truncate_to_budget(self, mock_git_repo: Path):
        """Text is truncated to fit token budget."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()

                # Create text that exceeds budget
                text = "a" * 1000  # ~250 tokens
                truncated = instance._truncate_to_budget(text, 100)

                # Should be truncated
                assert len(truncated) < len(text)
                assert "(truncated)" in truncated
            finally:
                os.chdir(original_dir)

    def test_truncate_preserves_under_budget(self, mock_git_repo: Path):
        """Text under budget is not truncated."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()

                text = "a" * 100  # ~25 tokens
                result = instance._truncate_to_budget(text, 100)

                assert result == text
            finally:
                os.chdir(original_dir)

    def test_truncate_at_natural_boundary(self, mock_git_repo: Path):
        """Truncation tries to end at natural boundaries."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()

                # Create multi-line text
                lines = ["line " + str(i) for i in range(100)]
                text = "\n".join(lines)
                truncated = instance._truncate_to_budget(text, 50)

                # Should end with truncation marker
                assert truncated.endswith("(truncated)")
            finally:
                os.chdir(original_dir)
