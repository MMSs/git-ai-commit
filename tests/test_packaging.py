"""Verify installed modules and default config survive wheel packaging."""

import os
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path


def test_wheel_entry_point_loads_outside_source_tree(tmp_path) -> None:
    project_dir = Path(__file__).parents[1]
    result = subprocess.run(
        ["uv", "build", "--offline", "--wheel", "--out-dir", str(tmp_path)],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    wheel_path = next(tmp_path.glob("*.whl"))
    venv_dir = tmp_path / "venv"
    for command in [
        ["uv", "venv", "--offline", "--python", sys.executable, str(venv_dir)],
        [
            "uv",
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--python",
            str(venv_dir / "bin" / "python"),
            str(wheel_path),
        ],
    ]:
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    # Reuse test-environment dependencies, without copying its editable app install.
    # The isolated venv's installed wheel precedes this extra dependency path.
    site_packages = (
        venv_dir
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    (site_packages / "test-dependencies.pth").write_text(
        sysconfig.get_path("purelib") + "\n"
    )
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [str(venv_dir / "bin" / "git-ai-commit")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "OPENAI_API_KEY environment variable is not set" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "Default configuration file not found" not in result.stderr
    wheel_dir = tmp_path / "installed"
    with zipfile.ZipFile(wheel_path) as wheel:
        assert "git_ai_commit_models.py" in wheel.namelist()
        assert "model_compatibility.py" not in wheel.namelist()
        wheel.extractall(wheel_dir)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); "
            "import git_ai_commit, git_ai_commit_models; "
            "assert Path(git_ai_commit.__file__).parent == Path(sys.argv[1]); "
            "assert Path(git_ai_commit_models.__file__).parent == Path(sys.argv[1]); "
            "assert git_ai_commit.DEFAULT_CONFIG['openai']['model'] == 'gpt-6-luna'; "
            "assert callable(git_ai_commit.main)",
            str(wheel_dir),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
