"""
Python-based tests for Zsh plugin patterns.

These tests verify the core logic patterns used in the Zsh plugin
without requiring zsh to be installed. They test:
1. Mode detection regex patterns
2. Output sanitization logic
3. Buffer manipulation patterns
"""

import re
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestModeDetectionPatterns:
    """Tests for mode detection patterns used in the Zsh plugin."""

    def detect_mode(self, cmd: str) -> tuple[str, str]:
        """
        Python implementation of the mode detection logic from the Zsh plugin.

        This mirrors the logic from git-ai-commit.plugin.zsh lines 134-150.
        """
        mode = ""
        partial_text = ""
        after_flag = ""

        # Extract portion after -m or --message flag
        match = re.search(r'(-m|--message)\s+(.*)', cmd)
        if match:
            after_flag = match.group(2)

        # Detect quote state and mode
        if not after_flag:
            mode = "generation"
        elif re.match(r'^"([^"]*)$', after_flag):
            mode = "completion"
            partial_match = re.match(r'^"([^"]*)$', after_flag)
            if partial_match:
                partial_text = partial_match.group(1)
        else:
            mode = "none"  # Closed quote or other pattern

        return mode, partial_text

    def test_generation_mode_no_quotes(self):
        """git commit -m (no quotes) triggers generation mode."""
        mode, partial = self.detect_mode("git commit -m ")
        assert mode == "generation"
        assert partial == ""

    def test_completion_mode_unclosed_quote(self):
        """git commit -m "text triggers completion mode."""
        mode, partial = self.detect_mode('git commit -m "feat:')
        assert mode == "completion"
        assert partial == "feat:"

    def test_closed_quote_no_trigger(self):
        """Closed quote should not trigger AI."""
        mode, partial = self.detect_mode('git commit -m "complete message"')
        assert mode == "none"

    def test_empty_unclosed_quote(self):
        """Empty unclosed quote triggers completion mode."""
        mode, partial = self.detect_mode('git commit -m "')
        assert mode == "completion"
        assert partial == ""

    def test_message_flag_long_form(self):
        """--message flag triggers generation mode."""
        mode, partial = self.detect_mode("git commit --message ")
        assert mode == "generation"

    def test_message_flag_with_quote(self):
        """--message with quote triggers completion mode."""
        mode, partial = self.detect_mode('git commit --message "fix:')
        assert mode == "completion"
        assert partial == "fix:"

    def test_partial_text_with_spaces(self):
        """Partial text with spaces is preserved."""
        mode, partial = self.detect_mode('git commit -m "feat: add user')
        assert mode == "completion"
        assert partial == "feat: add user"

    def test_flags_before_m(self):
        """Other flags before -m are handled."""
        mode, partial = self.detect_mode("git commit -a -m ")
        assert mode == "generation"

    def test_partial_with_parens(self):
        """Partial text with parentheses (scope) is preserved."""
        mode, partial = self.detect_mode('git commit -m "feat(auth):')
        assert mode == "completion"
        assert partial == "feat(auth):"


class TestSanitizationPatterns:
    """Tests for output sanitization patterns used in the Zsh plugin."""

    def sanitize_suggestion(self, suggestion: str) -> str:
        """
        Python implementation of the sanitization logic from the Zsh plugin.

        This mirrors the logic from git-ai-commit.plugin.zsh lines 231-236.
        Order matters: backslash must be escaped first!
        """
        if not suggestion:
            return suggestion

        # Must escape backslash first, then other special characters
        suggestion = suggestion.replace("\\", "\\\\")  # Backslash: \ -> \\
        suggestion = suggestion.replace('"', '\\"')    # Double quote: " -> \"
        suggestion = suggestion.replace("$", "\\$")    # Dollar sign: $ -> \$
        suggestion = suggestion.replace("`", "\\`")    # Backtick: ` -> \`

        return suggestion

    def test_plain_text_unchanged(self):
        """Plain text passes through unchanged."""
        text = "feat: add user authentication"
        assert self.sanitize_suggestion(text) == text

    def test_backslash_escaped(self):
        """Backslash is properly escaped."""
        assert self.sanitize_suggestion("fix: handle \\n in strings") == "fix: handle \\\\n in strings"

    def test_double_quote_escaped(self):
        """Double quote is properly escaped."""
        assert self.sanitize_suggestion('feat: add "quoted" string') == 'feat: add \\"quoted\\" string'

    def test_dollar_sign_escaped(self):
        """Dollar sign is properly escaped."""
        assert self.sanitize_suggestion("fix: handle $variable expansion") == "fix: handle \\$variable expansion"

    def test_backtick_escaped(self):
        """Backtick is properly escaped."""
        assert self.sanitize_suggestion("feat: add `code` blocks") == "feat: add \\`code\\` blocks"

    def test_multiple_special_chars(self):
        """Multiple special characters are all escaped."""
        input_text = 'fix: handle "$VAR" and `cmd`'
        expected = 'fix: handle \\"\\$VAR\\" and \\`cmd\\`'
        assert self.sanitize_suggestion(input_text) == expected

    def test_command_injection_neutralized(self):
        """Command injection attempt is neutralized."""
        assert self.sanitize_suggestion("feat: $(rm -rf /)") == "feat: \\$(rm -rf /)"

    def test_backtick_injection_neutralized(self):
        """Backtick command injection is neutralized."""
        assert self.sanitize_suggestion("feat: `rm -rf /`") == "feat: \\`rm -rf /\\`"

    def test_empty_string(self):
        """Empty string stays empty."""
        assert self.sanitize_suggestion("") == ""

    def test_backslash_before_quote(self):
        """Backslash before quote is handled correctly (order matters)."""
        # Input: \"
        # Step 1 (backslash): \\"
        # Step 2 (quote): \\\"
        assert self.sanitize_suggestion('\\"') == '\\\\\\"'


class TestBufferManipulationPatterns:
    """Tests for buffer manipulation patterns used in the Zsh plugin."""

    def update_buffer_generation(self, original_buffer: str, suggestion: str) -> str:
        """
        Python implementation of generation mode buffer update.

        This mirrors the logic from git-ai-commit.plugin.zsh line 253.
        """
        # Remove trailing space and wrap in quotes
        buffer = original_buffer.rstrip()
        return f'{buffer} "{suggestion}"'

    def update_buffer_completion(self, buffer: str, suggestion: str) -> str:
        """
        Python implementation of completion mode buffer update.

        This mirrors the logic from git-ai-commit.plugin.zsh line 249.
        """
        return buffer + suggestion

    def test_generation_adds_quotes(self):
        """Generation mode wraps suggestion in quotes."""
        result = self.update_buffer_generation("git commit -m ", "feat: add feature")
        assert result == 'git commit -m "feat: add feature"'

    def test_generation_removes_trailing_space(self):
        """Generation mode removes trailing whitespace."""
        result = self.update_buffer_generation("git commit -m   ", "feat: add feature")
        assert result == 'git commit -m "feat: add feature"'

    def test_completion_appends(self):
        """Completion mode appends without closing quote."""
        result = self.update_buffer_completion('git commit -m "feat:', " add user auth")
        assert result == 'git commit -m "feat: add user auth'

    def test_completion_preserves_content(self):
        """Completion mode preserves original content."""
        result = self.update_buffer_completion('git commit -m "feat(auth): add', " JWT tokens")
        assert result == 'git commit -m "feat(auth): add JWT tokens'

    def test_multiple_completions_chain(self):
        """Multiple completions can be chained."""
        buffer = 'git commit -m "feat:'
        buffer = self.update_buffer_completion(buffer, " add")
        buffer = self.update_buffer_completion(buffer, " login")
        buffer = self.update_buffer_completion(buffer, " feature")
        assert buffer == 'git commit -m "feat: add login feature'

    def test_generation_with_message_flag(self):
        """Generation works with --message flag."""
        result = self.update_buffer_generation("git commit --message ", "fix: resolve bug")
        assert result == 'git commit --message "fix: resolve bug"'

    def test_generation_with_other_flags(self):
        """Generation preserves other flags."""
        result = self.update_buffer_generation("git commit -a -m ", "feat: add feature")
        assert result == 'git commit -a -m "feat: add feature"'


class TestEndToEndPatterns:
    """End-to-end tests combining mode detection, sanitization, and buffer update."""

    def full_workflow(self, cmd: str, ai_response: str) -> tuple[str, str]:
        """
        Simulate the full plugin workflow.

        Returns: (mode, final_buffer)
        """
        # Mode detection
        mode = ""
        partial_text = ""
        after_flag = ""

        match = re.search(r'(-m|--message)\s+(.*)', cmd)
        if match:
            after_flag = match.group(2)

        if not after_flag:
            mode = "generation"
        elif re.match(r'^"([^"]*)$', after_flag):
            mode = "completion"
            partial_match = re.match(r'^"([^"]*)$', after_flag)
            if partial_match:
                partial_text = partial_match.group(1)
        else:
            mode = "none"
            return mode, cmd

        # Sanitize AI response
        suggestion = ai_response
        suggestion = suggestion.replace("\\", "\\\\")
        suggestion = suggestion.replace('"', '\\"')
        suggestion = suggestion.replace("$", "\\$")
        suggestion = suggestion.replace("`", "\\`")

        # Update buffer based on mode
        if mode == "generation":
            buffer = cmd.rstrip()
            final_buffer = f'{buffer} "{suggestion}"'
        else:  # completion
            final_buffer = cmd + suggestion

        return mode, final_buffer

    def test_generation_workflow(self):
        """Full workflow for generation mode."""
        mode, buffer = self.full_workflow("git commit -m ", "feat: add new feature")
        assert mode == "generation"
        assert buffer == 'git commit -m "feat: add new feature"'

    def test_completion_workflow(self):
        """Full workflow for completion mode."""
        mode, buffer = self.full_workflow('git commit -m "feat: add', " user authentication")
        assert mode == "completion"
        assert buffer == 'git commit -m "feat: add user authentication'

    def test_sanitization_in_workflow(self):
        """Sanitization works within full workflow."""
        # AI might return text with special characters
        mode, buffer = self.full_workflow("git commit -m ", 'fix: handle "$VAR" expansion')
        assert mode == "generation"
        assert '\\"' in buffer
        assert '\\$' in buffer

    def test_closed_quote_no_modification(self):
        """Closed quote returns unchanged buffer."""
        mode, buffer = self.full_workflow('git commit -m "done"', "ignored")
        assert mode == "none"
        assert buffer == 'git commit -m "done"'
