"""Verify chat-style wrappers are stripped from generated messages."""

import pytest

from git_ai_commit_backends import clean_output


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("feat: add login", "feat: add login"),
        ("feat: add login\n\n", "feat: add login"),
        ("```\nfeat: add login\n```", "feat: add login"),
        ("```text\nfeat: add login\n```\n", "feat: add login"),
        ("Here's the commit message:\n\nfeat: add login", "feat: add login"),
        ("Here is your commit message:\n```\nfeat: add login\n```", "feat: add login"),
        ('"feat: add login"', "feat: add login"),
        ('fix: handle "quoted" input', 'fix: handle "quoted" input'),
        (" with refresh tokens", " with refresh tokens"),
        (
            "feat: add login\n\n- add form\n- add session",
            "feat: add login\n\n- add form\n- add session",
        ),
    ],
)
def test_clean_output(raw: str, expected: str) -> None:
    assert clean_output(raw) == expected
