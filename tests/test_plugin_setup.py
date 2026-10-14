"""Verify dependency refresh and failures in plugin environment setup."""

import os
import shlex
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "sdk_current,uv_available,install_status,expected_status",
    [
        (True, True, 0, 0),
        (False, True, 0, 0),
        (False, False, 0, 0),
        (False, True, 1, 1),
        (False, False, 1, 1),
    ],
)
def test_setup_refreshes_old_sdk(
    tmp_path,
    sdk_current,
    uv_available,
    install_status,
    expected_status,
) -> None:
    plugin_dir = tmp_path / "plugin with spaces"
    venv_bin = plugin_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    command_log = tmp_path / "commands"
    python = venv_bin / "python"
    python.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "-c" ]; then exit {0 if sdk_current else 1}; fi\n'
        f"printf '%s\\n' \"$@\" >> {shlex.quote(str(command_log))}\n"
        f"exit {install_status}\n",
    )
    python.chmod(0o755)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    if uv_available:
        uv = mock_bin / "uv"
        uv.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" >> {shlex.quote(str(command_log))}\n"
            f"exit {install_status}\n",
        )
        uv.chmod(0o755)
    plugin_source = (Path(__file__).parents[1] / "git-ai-commit.plugin.zsh").read_text()
    setup_function = plugin_source.split("# Function to ensure virtualenv is set up\n")[
        1
    ]
    setup_function = setup_function.split("# Initialize the plugin")[0]
    script = (
        f"PLUGIN_DIR={shlex.quote(str(plugin_dir))}\n"
        f"{setup_function}\n_git_ai_commit_ensure_venv"
    )

    result = subprocess.run(
        ["/bin/zsh", "-f", "-c", script],
        env={**os.environ, "PATH": f"{mock_bin}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == expected_status, result.stderr
    if sdk_current:
        assert not command_log.exists()
    elif uv_available:
        assert command_log.read_text().splitlines() == [
            "sync",
            "--project",
            str(plugin_dir),
            "--no-dev",
        ]
    else:
        assert command_log.read_text().splitlines() == [
            "-m",
            "pip",
            "install",
            "--upgrade",
            str(plugin_dir),
        ]


@pytest.mark.parametrize(
    "uv_available,venv_status", [(True, 0), (False, 0), (False, 1)]
)
def test_fresh_environment_setup(tmp_path, uv_available, venv_status) -> None:
    plugin_dir = tmp_path / "fresh plugin"
    plugin_dir.mkdir()
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    command_log = tmp_path / "commands"
    installer = tmp_path / "installer"
    installer.write_text(
        "#!/bin/sh\n" f"printf '%s\\n' \"$@\" >> {shlex.quote(str(command_log))}\n",
    )
    installer.chmod(0o755)
    python3 = mock_bin / "python3"
    python3.write_text(
        "#!/bin/sh\n"
        f"if [ {venv_status} -ne 0 ]; then exit {venv_status}; fi\n"
        'mkdir -p "$3/bin"\n'
        f'cp {shlex.quote(str(installer))} "$3/bin/python"\n',
    )
    python3.chmod(0o755)
    if uv_available:
        (mock_bin / "uv").write_text(installer.read_text())
        (mock_bin / "uv").chmod(0o755)
    plugin_source = (Path(__file__).parents[1] / "git-ai-commit.plugin.zsh").read_text()
    function = plugin_source.split("# Function to ensure virtualenv is set up\n")[1]
    function = function.split("# Initialize the plugin")[0]

    result = subprocess.run(
        [
            "/bin/zsh",
            "-f",
            "-c",
            f"PLUGIN_DIR={shlex.quote(str(plugin_dir))}\n{function}\n_git_ai_commit_ensure_venv",
        ],
        env={**os.environ, "PATH": f"{mock_bin}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == (0 if uv_available else venv_status), result.stderr
    if not uv_available and venv_status:
        assert not command_log.exists()
    else:
        args = command_log.read_text().splitlines()
        if uv_available:
            assert args == ["sync", "--project", str(plugin_dir), "--no-dev"]
        else:
            assert args == ["-m", "pip", "install", "--upgrade", str(plugin_dir)]
