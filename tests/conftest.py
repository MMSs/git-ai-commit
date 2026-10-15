"""Shared fixtures: a fake CLI on PATH and a throwaway git repository."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FAKE_CLI = """\
import json
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
record = Path(os.environ["FAKE_RECORD"])
partial = record.with_suffix(".tmp")
partial.write_text(json.dumps({
    "argv": args,
    "cwd": os.getcwd(),
    "stdin": sys.stdin.read(),
    "pid": os.getpid(),
}))
os.replace(partial, record)
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
reply = os.environ.get("FAKE_REPLY", "feat: add thing")
if "-o" in args:
    Path(args[args.index("-o") + 1]).write_text(reply)
else:
    sys.stdout.write(reply)
sys.stderr.write(os.environ.get("FAKE_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put an executable ``fake-cli`` on PATH; return where it records its call."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "fake-cli"
    script.write_text(f"#!{sys.executable}\n{FAKE_CLI}")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_RECORD", str(record))
    return record


async def wait_for_record(record: Path) -> dict:
    for _ in range(200):
        if record.exists():
            return json.loads(record.read_text())
        await asyncio.sleep(0.05)
    raise AssertionError("fake CLI never started")


async def wait_until_dead(pid: int) -> None:
    for _ in range(200):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"process {pid} is still running")


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "app.py").write_text("print('hi')\n")
    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
    return repo
