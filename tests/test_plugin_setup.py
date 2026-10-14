"""Verify setup caching, offline recovery, and environment isolation."""

import os
import shlex
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def setup_harness(tmp_path):
    plugin_dir = tmp_path / "plugin with spaces"
    plugin_dir.mkdir()
    (plugin_dir / "pyproject.toml").write_text(
        '[project]\ndependencies = ["openai>=2.14.0"]\n'
    )
    (plugin_dir / "uv.lock").write_text("version = 1\n")
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    calls = tmp_path / "calls"
    python_calls = tmp_path / "python-calls"
    arguments = tmp_path / "arguments"
    environment = tmp_path / "environment"
    status_file = tmp_path / "install-status"
    status_file.write_text("0\n")
    install_log = (
        f"printf 'call\\n' >> {shlex.quote(str(calls))}\n"
        f"printf '%s\\n' \"$@\" >> {shlex.quote(str(arguments))}\n"
        f"IFS= read -r install_status < {shlex.quote(str(status_file))}\n"
        'if [ "$install_status" -ne 0 ]; then exit "$install_status"; fi\n'
    )
    stub = tmp_path / "python-stub"
    stub.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then\n'
        f"{install_log}exit 0\nfi\n"
        f"printf 'python\\n' >> {shlex.quote(str(python_calls))}\n",
    )
    stub.chmod(0o755)
    python3 = mock_bin / "python3"
    python3.write_text(
        "#!/bin/sh\n"
        f'if [ -f {shlex.quote(str(tmp_path / "venv-failure"))} ]; then exit 1; fi\n'
        'mkdir -p "$3/bin"\n'
        f'cp {shlex.quote(str(stub))} "$3/bin/python"\n',
    )
    python3.chmod(0o755)
    uv = mock_bin / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        f"{install_log}"
        f"printf '%s' \"$UV_PROJECT_ENVIRONMENT\" > {shlex.quote(str(environment))}\n"
        'mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"\n'
        f'cp {shlex.quote(str(stub))} "$UV_PROJECT_ENVIRONMENT/bin/python"\n',
    )
    uv.chmod(0o755)

    def run(*, retry: bool = False):
        source = (Path(__file__).parents[1] / "git-ai-commit.plugin.zsh").read_text()
        function = source.split("# Function to ensure virtualenv is set up\n")[1]
        function = function.split("# Initialize the plugin")[0]
        return subprocess.run(
            [
                "/bin/zsh",
                "-f",
                "-c",
                f"PLUGIN_DIR={shlex.quote(str(plugin_dir))}\n{function}\n"
                f"_git_ai_commit_ensure_venv {'--retry' if retry else ''}\n",
            ],
            env={
                **os.environ,
                "PATH": f"{mock_bin}:/usr/bin:/bin",
                "UV_PROJECT_ENVIRONMENT": str(tmp_path / "other-env"),
            },
            capture_output=True,
            text=True,
        )

    def seed_environment() -> None:
        venv_bin = plugin_dir / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").write_text(stub.read_text())
        (venv_bin / "python").chmod(0o755)

    return {
        "run": run,
        "seed": seed_environment,
        "plugin": plugin_dir,
        "calls": calls,
        "python_calls": python_calls,
        "arguments": arguments,
        "environment": environment,
        "status": status_file,
        "uv": uv,
    }


@pytest.mark.parametrize("uv_available", [True, False])
@pytest.mark.parametrize("existing", [True, False])
def test_successful_setup_is_cached(setup_harness, uv_available, existing) -> None:
    h = setup_harness
    if existing:
        h["seed"]()
    if not uv_available:
        h["uv"].unlink()

    first = h["run"]()
    second = h["run"]()

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert h["calls"].read_text().count("call\n") == 1
    assert not h["python_calls"].exists()
    assert (h["plugin"] / ".venv" / ".git-ai-commit-ready").exists()
    if uv_available:
        assert h["environment"].read_text() == str(h["plugin"] / ".venv")
        assert h["arguments"].read_text().splitlines() == [
            "sync",
            "--project",
            str(h["plugin"]),
            "--no-dev",
            "--locked",
        ]
    else:
        assert h["arguments"].read_text().splitlines() == [
            "-m",
            "pip",
            "install",
            "--upgrade",
            str(h["plugin"]),
        ]


@pytest.mark.parametrize("dependency_file", ["uv.lock", "pyproject.toml"])
def test_dependency_changes_refresh_once(setup_harness, dependency_file) -> None:
    h = setup_harness
    assert h["run"]().returncode == 0
    path = h["plugin"] / dependency_file
    path.write_text(path.read_text() + "# dependency changed\n")

    assert h["run"]().returncode == 0
    assert h["run"]().returncode == 0
    assert h["calls"].read_text().count("call\n") == 2
    assert not h["python_calls"].exists()


@pytest.mark.parametrize("uv_available", [True, False])
def test_failed_refresh_keeps_existing_environment(setup_harness, uv_available) -> None:
    h = setup_harness
    h["seed"]()
    if not uv_available:
        h["uv"].unlink()
    h["status"].write_text("1\n")

    first = h["run"]()
    second = h["run"]()

    assert first.returncode == 0
    assert second.returncode == 0
    assert h["calls"].read_text().count("call\n") == 1
    assert "--retry" in first.stderr
    assert not (h["plugin"] / ".venv" / ".git-ai-commit-ready").exists()
    h["status"].write_text("0\n")
    assert h["run"](retry=True).returncode == 0
    assert h["run"]().returncode == 0
    assert h["calls"].read_text().count("call\n") == 2


@pytest.mark.parametrize("uv_available", [True, False])
def test_failed_fresh_install_requires_explicit_retry(
    setup_harness, uv_available
) -> None:
    h = setup_harness
    if not uv_available:
        h["uv"].unlink()
    h["status"].write_text("1\n")

    assert h["run"]().returncode == 1
    assert h["run"]().returncode == 1
    assert h["calls"].read_text().count("call\n") == 1
    assert h["run"](retry=True).returncode == 1
    assert h["calls"].read_text().count("call\n") == 2
    h["status"].write_text("0\n")
    assert h["run"](retry=True).returncode == 0
    assert h["calls"].read_text().count("call\n") == 3


def test_failed_venv_creation_is_not_repeated(setup_harness, tmp_path) -> None:
    h = setup_harness
    h["uv"].unlink()
    (tmp_path / "venv-failure").touch()

    assert h["run"]().returncode == 1
    assert h["run"]().returncode == 1
    assert not h["calls"].exists()
    (tmp_path / "venv-failure").unlink()
    assert h["run"](retry=True).returncode == 0
    assert h["calls"].read_text().count("call\n") == 1


@pytest.mark.parametrize("uv_available", [True, False])
@pytest.mark.parametrize("repair_status", [0, 1])
def test_missing_interpreter_invalidates_ready_marker(
    setup_harness, uv_available, repair_status
) -> None:
    h = setup_harness
    if not uv_available:
        h["uv"].unlink()
    assert h["run"]().returncode == 0
    (h["plugin"] / ".venv" / "bin" / "python").unlink()
    h["status"].write_text(f"{repair_status}\n")

    assert h["run"]().returncode == repair_status
    assert h["run"]().returncode == repair_status
    assert h["calls"].read_text().count("call\n") == 2
    if repair_status:
        h["status"].write_text("0\n")
        assert h["run"](retry=True).returncode == 0
        assert h["run"]().returncode == 0
        assert h["calls"].read_text().count("call\n") == 3
