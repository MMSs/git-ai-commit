"""Verify lazygit reuses plugin Python without syncing another environment."""

import os
import shlex
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("generation_status", [0, 1])
def test_lazygit_uses_plugin_interpreter(tmp_path, generation_status) -> None:
    custom_dir = tmp_path / "custom directory"
    plugin_dir = custom_dir / "plugins" / "git-ai-commit"
    venv_bin = plugin_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    python_args = tmp_path / "python-args"
    python = venv_bin / "python"
    python.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(str(python_args))}\n"
        "printf 'fix: handle input\\n'\n"
        f"exit {generation_status}\n",
    )
    python.chmod(0o755)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    forbidden_calls = tmp_path / "forbidden-calls"
    for command in ["uv", "git"]:
        executable = mock_bin / command
        executable.write_text(
            "#!/bin/sh\n"
            f"printf '{command}\\n' >> {shlex.quote(str(forbidden_calls))}\nexit 1\n",
        )
        executable.chmod(0o755)
    editor = mock_bin / "editor"
    editor.write_text('#!/bin/sh\n: > "$1"\n')
    editor.chmod(0o755)
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git").mkdir(parents=True)

    result = subprocess.run(
        [
            "/bin/bash",
            str(Path(__file__).parents[1] / "bin" / "lazygit-generate-commit.sh"),
        ],
        cwd=repo_dir,
        env={
            **os.environ,
            "ZSH_CUSTOM": str(custom_dir),
            "UV_PROJECT_ENVIRONMENT": str(tmp_path / "unrelated-env"),
            "EDITOR": str(editor),
            "PATH": f"{mock_bin}:/usr/bin:/bin",
        },
        input="\n",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    expected = "Commit aborted" if generation_status == 0 else "Failed to generate"
    assert expected in result.stdout
    assert python_args.read_text().strip() == str(
        plugin_dir / "src" / "git_ai_commit.py"
    )
    assert not forbidden_calls.exists()
    assert not list((repo_dir / ".git").glob("COMMIT_EDITMSG.*"))
