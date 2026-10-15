# Command Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users generate commit messages with a local CLI (claude, codex, cursor-agent, ollama, …) through a generic `command` backend, alongside the existing OpenAI API backend.

**Architecture:** A new module `src/git_ai_commit_backends.py` owns backend selection and execution. `GitAICommit` keeps building prompts exactly as today and hands `(system_prompt, user_prompt)` to a backend object with one method, `complete()`. `ApiBackend` wraps the existing OpenAI call; `CommandBackend` runs a user-configured argv as a subprocess. Config moves from a top-level `openai:` block to `api:` (legacy blocks are mapped silently) and gains `backend:` and `command:`.

**Tech Stack:** Python 3.11+, asyncio subprocesses, PyYAML, OpenAI SDK, pytest + pytest-asyncio (`asyncio_mode = "auto"`), uv.

**Spec:** No separate spec file. The design was agreed in conversation on 2026-10-15 and is restated in full under *Design* below.

## Design

```yaml
backend: api                 # api (default) | command

api:
  provider: openai           # only "openai" is supported for now
  model: gpt-6-luna
  reasoning_effort: none
  temperature: 0.7
  max_tokens: 0

command:
  argv: ["claude", "-p", "--output-format", "text", "--model", "haiku"]
  timeout_seconds: 60
```

- Backend selection precedence: `--backend` CLI flag > `GIT_AI_COMMIT_BACKEND` env var > project config > global config > default `api`.
- Legacy top-level `openai:` blocks (global or project, YAML or JSON) are silently moved under `api:` with `provider: openai`. When one file has both, keys under `api:` win.
- `OPENAI_API_KEY` is required only when the backend is `api`.
- `command.argv` placeholders, each substituted inside individual argv items (no shell):

| Placeholder | Meaning | If absent |
|---|---|---|
| `{prompt}` | Prompt passed as an argument | Prompt sent on **stdin** |
| `{system_prompt}` | System prompt passed as an argument | System prompt prepended to the prompt, separated by a blank line |
| `{output_file}` | Temp file path the CLI writes its answer to | Answer read from **stdout** |

- Command runner: `asyncio.create_subprocess_exec` (never a shell), cwd is a fresh empty temp dir, own process group (`start_new_session=True`), the whole group is killed on timeout and on cancellation (Ctrl+C / SIGTERM), non-zero exit surfaces stderr, empty output is an error.
- Output cleanup (both backends): strip a "Here's the commit message:" preamble line, a wrapping code fence, trailing whitespace, and one pair of wrapping double quotes. Leading spaces are preserved (completion mode relies on them).
- Docs ship recipes for claude, codex, cursor-agent and ollama using plain-text output.
- Zsh loading text names the backend when `GIT_AI_COMMIT_BACKEND` is set.

## Global Constraints

- Python floor stays `>=3.11`; no new runtime dependencies.
- Never run the command through a shell (`shell=True`, `sh -c`, `os.system`).
- Default behaviour with no config changes must be byte-for-byte the same request to OpenAI as today.
- Error message for a missing key stays exactly `OPENAI_API_KEY environment variable is not set` (asserted by `tests/test_packaging.py`).
- Error messages reach the user via stderr as `Error: <message>` (existing `print_output(..., is_error=True)` convention).
- Black line length 88; ruff and mypy must pass: `uv run black src/ tests/ && uv run ruff check src/ && uv run mypy src/`.
- Commit messages: conventional style, lowercase imperative, **no `Co-Authored-By` or any trailer**.

## Review Focus

1. **Huge diffs** — a prompt of several hundred KB must reach the CLI intact via stdin (argv would hit `ARG_MAX`). Test: `test_large_prompt_goes_through_stdin` (Task 3).
2. **Ctrl+C / SIGTERM mid-generation** — the user expects no orphaned agent process left running. Tests: `test_cancel_kills_command` (Task 3), `test_interrupting_generation_kills_command` (Task 4).
3. **Mixed old and new config files** — global `openai:` plus project `api:` must merge as if both were `api:`. Test: `test_legacy_global_and_new_project_config_merge` (Task 1).
4. **Split command config** — global sets `command.timeout_seconds`, project sets only `backend` and `command.argv`; both must apply. Test: `test_command_config_merges_across_files` (Task 4).
5. **Hand-written argv mistakes** — `argv: claude -p` (a string) or `~/bin/my-cli` must give a clear error or just work, respectively. Tests: `test_argv_must_be_a_list` and `test_tilde_in_executable_is_expanded` (Task 3).

---

### Task 1: Move `openai` config under `api` with legacy mapping

**Files:**
- Create: `src/git_ai_commit_backends.py`
- Modify: `config/default_config.yaml` (the `# OpenAI API settings` block)
- Modify: `src/git_ai_commit.py:14-16` (imports), `:241-264` (`_load_config_file`), `:270` (docstring), `:1169` (`model_parameters` call)
- Modify: `tests/test_git_ai_commit_models.py:19`, `:173`, `:229-248`
- Modify: `tests/test_packaging.py:73-82`
- Test: `tests/test_git_ai_commit_backends.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `normalize_legacy_config(config: Any) -> Any` in `git_ai_commit_backends`; `DEFAULT_CONFIG["api"]` with keys `provider, model, temperature, max_tokens, reasoning_effort`; `GitAICommit.config["api"]` replaces `config["openai"]` everywhere.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_git_ai_commit_backends.py`:

```python
"""Verify backend configuration, selection and the API backend."""

from pathlib import Path
from unittest.mock import Mock

from git_ai_commit import DEFAULT_CONFIG, GitAICommit
from git_ai_commit_backends import normalize_legacy_config


def load_config(tmp_path: Path, monkeypatch, global_yaml: str, project_yaml: str):
    config_dir = tmp_path / ".config" / "git-ai-commit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(global_yaml)
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git-ai-commit.yaml").write_text(project_yaml)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    committer = GitAICommit.__new__(GitAICommit)
    committer._get_repo_path = Mock(return_value=repo_dir)
    return committer._load_config()


def test_default_config_uses_api_block() -> None:
    assert "openai" not in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["api"]["provider"] == "openai"
    assert DEFAULT_CONFIG["api"]["model"] == "gpt-6-luna"


def test_legacy_openai_block_moves_under_api() -> None:
    assert normalize_legacy_config({"openai": {"model": "gpt-5-nano"}}) == {
        "api": {"provider": "openai", "model": "gpt-5-nano"}
    }


def test_api_keys_win_over_legacy_keys_in_same_file() -> None:
    config = {
        "openai": {"model": "gpt-5-nano", "temperature": 0.2},
        "api": {"model": "gpt-6-luna"},
    }

    assert normalize_legacy_config(config) == {
        "api": {"provider": "openai", "model": "gpt-6-luna", "temperature": 0.2}
    }


def test_config_without_legacy_block_is_unchanged() -> None:
    config = {"api": {"model": "gpt-6-luna"}}

    assert normalize_legacy_config(config) is config


def test_non_mapping_config_is_passed_through() -> None:
    assert normalize_legacy_config(["not", "a", "mapping"]) == ["not", "a", "mapping"]


def test_legacy_global_and_new_project_config_merge(tmp_path, monkeypatch) -> None:
    config = load_config(
        tmp_path,
        monkeypatch,
        global_yaml="openai:\n  model: gpt-6-luna\n  reasoning_effort: low\n",
        project_yaml="api:\n  model: gpt-5-nano\n",
    )

    assert "openai" not in config
    assert config["api"]["provider"] == "openai"
    assert config["api"]["model"] == "gpt-5-nano"
    assert config["api"]["reasoning_effort"] == "low"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_ai_commit_backends.py -v`
Expected: collection ERROR with `ModuleNotFoundError: No module named 'git_ai_commit_backends'`.

- [ ] **Step 3: Create the module**

Create `src/git_ai_commit_backends.py`:

```python
"""Select and run the backend that turns prompts into a commit message."""

from typing import Any


def normalize_legacy_config(config: Any) -> Any:
    """Move a legacy top-level ``openai`` block under ``api``; ``api`` keys win."""
    if not isinstance(config, dict) or "openai" not in config:
        return config
    normalized = dict(config)
    legacy = normalized.pop("openai")
    if not isinstance(legacy, dict):
        return normalized
    api = normalized.get("api")
    normalized["api"] = {
        "provider": "openai",
        **legacy,
        **(api if isinstance(api, dict) else {}),
    }
    return normalized
```

- [ ] **Step 4: Rename the default config block**

In `config/default_config.yaml`, replace the two lines

```yaml
# OpenAI API settings
```
and
```yaml
openai:
  model: gpt-6-luna
```

with

```yaml
# API backend settings
```
and
```yaml
api:
  # Provider: only "openai" is supported for now
  provider: openai

  model: gpt-6-luna
```

Leave the model list comments and the `temperature`, `max_tokens`, `reasoning_effort` entries (and their comments) exactly as they are, indented under `api:`.

- [ ] **Step 5: Apply the mapping when loading each config file**

In `src/git_ai_commit.py`, add the import after line 16 (`from git_ai_commit_models import model_parameters`):

```python
from git_ai_commit_backends import normalize_legacy_config
```

Replace the body of `_load_config_file` (`src/git_ai_commit.py:241-264`) with:

```python
    def _load_config_file(self, path: Path) -> Dict:
        """Load a config file (JSON or YAML based on extension).

        JSON support maintained for backward compatibility only.
        Legacy top-level ``openai`` blocks are moved under ``api``.
        """
        try:
            with open(path) as f:
                if path.suffix in [".yaml", ".yml"]:
                    raw = yaml.safe_load(f) or {}
                else:  # .json - backward compatibility only
                    # Warn users about JSON deprecation
                    print_output(
                        f"Warning: JSON config detected at {path}. "
                        f"JSON configs are deprecated and may be removed in a future version. "
                        f"Please migrate to YAML format (.yaml or .yml).",
                        is_error=True,
                    )
                    raw = json.load(f)
            return normalize_legacy_config(raw)
        except (json.JSONDecodeError, yaml.YAMLError, IOError) as e:
            # Log error but don't crash - return empty dict
            print_output(
                f"Warning: Failed to load config from {path}: {e}", is_error=True
            )
            return {}
```

In the `_merge_config` docstring (`:270`), change `overriding only openai.model` to `overriding only api.model`.

At `:1169`, change `**model_parameters(self.config["openai"]),` to `**model_parameters(self.config["api"]),`.

- [ ] **Step 6: Update existing tests to the new key**

In `tests/test_git_ai_commit_models.py`:
- line 19: `"openai": {` → `"api": {` and add `"provider": "openai",` as the first key inside it.
- line 173: `committer.config["openai"]["max_tokens"]` → `committer.config["api"]["max_tokens"]`.
- In `test_config_precedence_keeps_effort_compatible` (`:229-248`), keep both YAML strings using `openai:` (this now doubles as a legacy-mapping test) and change the four `config["openai"]` reads to `config["api"]`.

In `tests/test_packaging.py`:
- after `assert "git_ai_commit_models.py" in wheel.namelist()` add `assert "git_ai_commit_backends.py" in wheel.namelist()`.
- in the `-c` script, change `"import git_ai_commit, git_ai_commit_models; "` to `"import git_ai_commit, git_ai_commit_backends, git_ai_commit_models; "`, add the line `"assert Path(git_ai_commit_backends.__file__).parent == Path(sys.argv[1]); "` after the `git_ai_commit_models` path assertion, and change `DEFAULT_CONFIG['openai']['model']` to `DEFAULT_CONFIG['api']['model']`.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests pass (133 existing + 6 new).

- [ ] **Step 8: Commit**

```bash
git add config/default_config.yaml src/git_ai_commit.py src/git_ai_commit_backends.py tests/
git commit -m "refactor(config): move openai settings under api with legacy mapping"
```

---

### Task 2: Shared output cleanup

**Files:**
- Modify: `src/git_ai_commit_backends.py` (add `clean_output`)
- Modify: `src/git_ai_commit.py:17` (import), `:1178` (`suggestion = ...`)
- Test: `tests/test_output_cleanup.py`, `tests/test_git_ai_commit_models.py` (one new test)

**Interfaces:**
- Consumes: `git_ai_commit_backends` module from Task 1.
- Produces: `clean_output(text: str) -> str` in `git_ai_commit_backends`; `GitAICommit.generate_suggestion()` returns cleaned text.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_output_cleanup.py`:

```python
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
```

Append to `tests/test_git_ai_commit_models.py`:

```python
async def test_generated_message_is_cleaned() -> None:
    committer = make_committer("gpt-6-luna", "none")
    response = committer.client.chat.completions.create.return_value
    response.choices[0].message.content = "```\nfix: handle input\n```\n"

    assert await committer.generate_suggestion() == "fix: handle input"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_output_cleanup.py tests/test_git_ai_commit_models.py::test_generated_message_is_cleaned -v`
Expected: `ImportError: cannot import name 'clean_output'`.

- [ ] **Step 3: Implement `clean_output`**

In `src/git_ai_commit_backends.py`, add `import re` above `from typing import Any`, then append:

```python
_PREAMBLE = re.compile(r"\A\s*here(?:'s| is)\b[^\n]*:[ \t]*\n+", re.IGNORECASE)
_FENCE = re.compile(r"\A\s*```[^\n]*\n(.*?)\n?```\s*\Z", re.DOTALL)


def clean_output(text: str) -> str:
    """Strip wrappers that chat-style models add around a commit message.

    Leading spaces are kept: completion mode continues the user's text.
    """
    text = _PREAMBLE.sub("", text, count=1)
    fence = _FENCE.match(text)
    if fence:
        text = fence.group(1)
    text = text.rstrip()
    body = text.lstrip()
    if len(body) >= 2 and body[0] == body[-1] == '"' and body.count('"') == 2:
        text = body[1:-1]
    return text
```

- [ ] **Step 4: Use it in `generate_suggestion`**

In `src/git_ai_commit.py`, change the import to:

```python
from git_ai_commit_backends import clean_output, normalize_legacy_config
```

and change `suggestion = response.choices[0].message.content or ""` to:

```python
            suggestion = clean_output(response.choices[0].message.content or "")
```

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/git_ai_commit.py src/git_ai_commit_backends.py tests/
git commit -m "feat: strip chat wrappers from generated messages"
```

---

### Task 3: `CommandBackend` subprocess runner

**Files:**
- Modify: `src/git_ai_commit_backends.py` (add `BackendError`, `CommandBackend`, helpers)
- Create: `tests/conftest.py` (fake CLI fixture and helpers)
- Test: `tests/test_command_backend.py`

**Interfaces:**
- Consumes: nothing from earlier tasks besides the module.
- Produces:
  - `class BackendError(Exception)`
  - `DEFAULT_TIMEOUT_SECONDS = 60`
  - `@dataclass(frozen=True) class CommandBackend(argv: tuple[str, ...], timeout_seconds: float = 60)`
  - `CommandBackend.from_config(config: dict[str, Any]) -> CommandBackend` (raises `ValueError` on bad config)
  - `async CommandBackend.complete(self, *, system_prompt: str, user_prompt: str) -> str` (raises `BackendError`; returns raw text, cleanup happens in `generate_suggestion`)
  - `tests/conftest.py`: fixture `fake_cli` → `Path` of the JSON record file; async helpers `wait_for_record(record: Path) -> dict` and `wait_until_dead(pid: int) -> None`; `make_repo(tmp_path: Path) -> Path`.

- [ ] **Step 1: Write the fake CLI fixture**

Create `tests/conftest.py`:

```python
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
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_command_backend.py`:

```python
"""Verify the command backend runs local CLIs safely."""

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

from conftest import wait_for_record, wait_until_dead
from git_ai_commit_backends import BackendError, CommandBackend


def backend(*argv: str, timeout_seconds: float = 60) -> CommandBackend:
    return CommandBackend.from_config(
        {"argv": list(argv), "timeout_seconds": timeout_seconds}
    )


async def run(command: CommandBackend) -> str:
    return await command.complete(system_prompt="SYS", user_prompt="USER")


async def test_prompt_goes_to_stdin_with_system_prompt_inlined(fake_cli) -> None:
    assert await run(backend("fake-cli", "-p")) == "feat: add thing"

    record = json.loads(fake_cli.read_text())
    assert record["argv"] == ["-p"]
    assert record["stdin"] == "SYS\n\nUSER"


async def test_system_prompt_placeholder_moves_it_to_argv(fake_cli) -> None:
    await run(backend("fake-cli", "--system-prompt", "{system_prompt}"))

    record = json.loads(fake_cli.read_text())
    assert record["argv"] == ["--system-prompt", "SYS"]
    assert record["stdin"] == "USER"


async def test_prompt_placeholder_moves_prompt_to_argv(fake_cli) -> None:
    await run(backend("fake-cli", "--prompt={prompt}"))

    record = json.loads(fake_cli.read_text())
    assert record["argv"] == ["--prompt=SYS\n\nUSER"]
    assert record["stdin"] == ""


async def test_placeholder_text_inside_prompts_is_not_substituted(fake_cli) -> None:
    command = backend("fake-cli", "{system_prompt}", "{prompt}")

    await command.complete(system_prompt="use {prompt}", user_prompt="diff")

    record = json.loads(fake_cli.read_text())
    assert record["argv"] == ["use {prompt}", "diff"]


async def test_other_braces_are_left_alone(fake_cli) -> None:
    await run(backend("fake-cli", '{"a": 1}'))

    assert json.loads(fake_cli.read_text())["argv"] == ['{"a": 1}']


async def test_output_file_placeholder_reads_answer_from_file(
    fake_cli, monkeypatch
) -> None:
    monkeypatch.setenv("FAKE_REPLY", "fix: from file")

    assert await run(backend("fake-cli", "-o", "{output_file}")) == "fix: from file"


async def test_command_runs_in_empty_temp_dir(fake_cli) -> None:
    await run(backend("fake-cli"))

    cwd = Path(json.loads(fake_cli.read_text())["cwd"])
    assert cwd.name.startswith("git-ai-commit-")
    assert cwd.resolve() != Path.cwd().resolve()
    assert not cwd.exists()


async def test_large_prompt_goes_through_stdin(fake_cli) -> None:
    command = backend("fake-cli")

    await command.complete(system_prompt="SYS", user_prompt="x" * 500_000)

    assert len(json.loads(fake_cli.read_text())["stdin"]) == 500_005


async def test_missing_executable_has_clear_error() -> None:
    with pytest.raises(BackendError, match="command 'nope-cli' not found on PATH"):
        await run(backend("nope-cli"))


async def test_non_executable_file_has_clear_error(tmp_path) -> None:
    script = tmp_path / "not-executable"
    script.write_text("echo hi\n")

    with pytest.raises(BackendError, match="is not executable"):
        await run(backend(str(script)))


async def test_non_zero_exit_reports_status_and_stderr(fake_cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_EXIT", "3")
    monkeypatch.setenv("FAKE_STDERR", "not logged in")

    with pytest.raises(BackendError, match="exited with status 3: not logged in"):
        await run(backend("fake-cli"))


async def test_empty_output_is_an_error(fake_cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_REPLY", "  \n")

    with pytest.raises(BackendError, match="command 'fake-cli' returned no output"):
        await run(backend("fake-cli"))


async def test_timeout_kills_command(fake_cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_SLEEP", "30")
    started = time.monotonic()

    with pytest.raises(BackendError, match="timed out after 0.5s"):
        await run(backend("fake-cli", timeout_seconds=0.5))

    assert time.monotonic() - started < 5
    await wait_until_dead(json.loads(fake_cli.read_text())["pid"])


async def test_cancel_kills_command(fake_cli, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_SLEEP", "30")
    task = asyncio.create_task(run(backend("fake-cli")))
    record = await wait_for_record(fake_cli)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    await wait_until_dead(record["pid"])


async def test_tilde_in_executable_is_expanded(fake_cli, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert await run(backend("~/bin/fake-cli")) == "feat: add thing"


def test_default_timeout_is_sixty_seconds() -> None:
    assert CommandBackend.from_config({"argv": ["x"]}).timeout_seconds == 60


@pytest.mark.parametrize("config", [{}, {"argv": None}, {"argv": []}])
def test_missing_argv_has_clear_error(config) -> None:
    with pytest.raises(
        ValueError, match="backend is 'command' but command.argv is not set"
    ):
        CommandBackend.from_config(config)


@pytest.mark.parametrize("argv", ["claude -p", ["claude", 3], [""], [" "]])
def test_argv_must_be_a_list(argv) -> None:
    with pytest.raises(ValueError, match="command.argv must be a list of strings"):
        CommandBackend.from_config({"argv": argv})


def test_empty_string_arguments_are_allowed() -> None:
    command = CommandBackend.from_config({"argv": ["claude", "--tools", ""]})

    assert command.argv == ("claude", "--tools", "")


@pytest.mark.parametrize("timeout", [0, -1, "60", True, None])
def test_timeout_must_be_positive_number(timeout) -> None:
    with pytest.raises(
        ValueError, match="command.timeout_seconds must be a positive number"
    ):
        CommandBackend.from_config({"argv": ["x"], "timeout_seconds": timeout})
```

Note: `500_005` is `len("SYS\n\n") + 500_000`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_command_backend.py -v`
Expected: `ImportError: cannot import name 'BackendError'`.

- [ ] **Step 4: Implement `CommandBackend`**

In `src/git_ai_commit_backends.py`, replace the imports at the top with:

```python
import asyncio
import contextlib
import os
import re
import signal
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
```

Append to the module:

```python
DEFAULT_TIMEOUT_SECONDS = 60
PROMPT = "{prompt}"
SYSTEM_PROMPT = "{system_prompt}"
OUTPUT_FILE = "{output_file}"
_PLACEHOLDER = re.compile(r"\{(?:prompt|system_prompt|output_file)\}")
_STDERR_LIMIT = 500


class BackendError(Exception):
    """A backend could not produce a commit message."""


@dataclass(frozen=True)
class CommandBackend:
    """Run a local CLI that reads a prompt and prints a commit message."""

    argv: tuple[str, ...]
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "CommandBackend":
        argv = config.get("argv")
        if argv is None or argv == []:
            raise ValueError("backend is 'command' but command.argv is not set")
        if (
            not isinstance(argv, list)
            or not all(isinstance(arg, str) for arg in argv)
            or not argv[0].strip()
        ):
            raise ValueError(
                "command.argv must be a list of strings, "
                'e.g. ["claude", "-p", "--output-format", "text"]'
            )
        timeout = config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError("command.timeout_seconds must be a positive number")
        return cls(
            argv=(os.path.expanduser(argv[0]), *argv[1:]),
            timeout_seconds=float(timeout),
        )

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        with tempfile.TemporaryDirectory(prefix="git-ai-commit-") as workdir:
            output_path = Path(workdir) / "message.txt"
            argv, stdin_text = self._render(system_prompt, user_prompt, output_path)
            output = await self._run(argv, stdin_text, cwd=workdir)
            if self._uses(OUTPUT_FILE):
                output = (
                    output_path.read_text(errors="replace")
                    if output_path.exists()
                    else ""
                )
        if not output.strip():
            raise BackendError(f"command '{self.argv[0]}' returned no output")
        return output

    def _uses(self, placeholder: str) -> bool:
        return any(placeholder in arg for arg in self.argv)

    def _render(
        self, system_prompt: str, user_prompt: str, output_path: Path
    ) -> tuple[list[str], str | None]:
        """Substitute placeholders; return argv and the text to send on stdin."""
        prompt = (
            user_prompt
            if self._uses(SYSTEM_PROMPT)
            else f"{system_prompt}\n\n{user_prompt}"
        )
        values = {
            PROMPT: prompt,
            SYSTEM_PROMPT: system_prompt,
            OUTPUT_FILE: str(output_path),
        }
        # One pass per argument, so placeholder text inside prompts stays literal.
        argv = [
            _PLACEHOLDER.sub(lambda match: values[match.group(0)], arg)
            for arg in self.argv
        ]
        return argv, None if self._uses(PROMPT) else prompt

    async def _run(self, argv: list[str], stdin_text: str | None, *, cwd: str) -> str:
        name = argv[0]
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                stdin=(
                    asyncio.subprocess.PIPE
                    if stdin_text is not None
                    else asyncio.subprocess.DEVNULL
                ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Own process group, so timeouts and Ctrl+C reach agent subprocesses.
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise BackendError(f"command '{name}' not found on PATH") from exc
        except PermissionError as exc:
            raise BackendError(f"command '{name}' is not executable") from exc

        stdin_bytes = stdin_text.encode() if stdin_text is not None else None
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(stdin_bytes), self.timeout_seconds
            )
        except TimeoutError as exc:
            _kill_process_group(process)
            await process.wait()
            raise BackendError(
                f"command '{name}' timed out after {self.timeout_seconds:g}s"
            ) from exc
        except BaseException:
            # Cancellation from Ctrl+C or SIGTERM must not leave the CLI running.
            _kill_process_group(process)
            raise

        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()[-_STDERR_LIMIT:]
            raise BackendError(
                f"command '{name}' exited with status {process.returncode}: "
                f"{detail or 'no error output'}"
            )
        return stdout.decode(errors="replace")


def _kill_process_group(process: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGKILL)
```

- [ ] **Step 5: Run the new tests**

Run: `uv run pytest tests/test_command_backend.py -v`
Expected: all PASS. If `test_non_executable_file_has_clear_error` fails with a different `OSError` subclass on this platform, add that subclass to the `PermissionError` branch rather than loosening the test.

- [ ] **Step 6: Run the full suite and linters**

Run: `uv run pytest -q && uv run black src/ tests/ && uv run ruff check src/ && uv run mypy src/`
Expected: all pass, no lint/type errors.

- [ ] **Step 7: Commit**

```bash
git add src/git_ai_commit_backends.py tests/conftest.py tests/test_command_backend.py
git commit -m "feat: add command backend for running local cli tools"
```

---

### Task 4: Backend selection, `ApiBackend`, and wiring into `GitAICommit`

**Files:**
- Modify: `src/git_ai_commit_backends.py` (add `Backend`, `ApiBackend`, `resolve_backend`, `build_backend`, constants)
- Modify: `src/git_ai_commit.py:1-17` (imports), `:188-193` (`__init__`), `:1129-1195` (`generate_suggestion`), `:1198-1210` (`main`)
- Modify: `config/default_config.yaml` (add `backend` and `command` sections above `api`)
- Modify: `tests/test_git_ai_commit_models.py` (`make_committer`, `committer.client` references, real-SDK test)
- Test: `tests/test_git_ai_commit_backends.py` (append)

**Interfaces:**
- Consumes: `CommandBackend.from_config`, `BackendError` (Task 3); `clean_output` (Task 2); `normalize_legacy_config` (Task 1); `make_repo`, `fake_cli`, `wait_for_record`, `wait_until_dead` (Task 3 conftest).
- Produces:
  - `BACKEND_ENV_VAR = "GIT_AI_COMMIT_BACKEND"`, `VALID_BACKENDS = ("api", "command")`, `SUPPORTED_API_PROVIDERS = ("openai",)`
  - `class Backend(Protocol)` with `async complete(self, *, system_prompt: str, user_prompt: str) -> str`
  - `class ApiBackend(config: dict[str, Any], *, client: AsyncOpenAI | None = None)` with attributes `config`, `client`
  - `resolve_backend(config: dict[str, Any], override: str | None = None) -> str`
  - `build_backend(config: dict[str, Any], name: str) -> Backend`
  - `GitAICommit(*, backend: str | None = None)` with attribute `backend: Backend` (no more `client`)
  - `main(argv: list[str] | None = None) -> int` accepting `--backend {api,command}`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_git_ai_commit_backends.py` (merge the new imports into the existing import block at the top):

```python
import signal
import subprocess
import sys

import pytest

from conftest import make_repo, wait_for_record, wait_until_dead
from git_ai_commit import main
from git_ai_commit_backends import (
    ApiBackend,
    CommandBackend,
    build_backend,
    resolve_backend,
)

SCRIPT = Path(__file__).parents[1] / "src" / "git_ai_commit.py"


@pytest.fixture(autouse=True)
def no_backend_env(monkeypatch) -> None:
    monkeypatch.delenv("GIT_AI_COMMIT_BACKEND", raising=False)


@pytest.mark.parametrize(
    "override,env,configured,expected",
    [
        ("command", "api", "api", "command"),
        (None, "command", "api", "command"),
        (None, None, "command", "command"),
        (None, None, None, "api"),
        (None, " Command ", None, "command"),
    ],
)
def test_backend_precedence(override, env, configured, expected, monkeypatch) -> None:
    if env is not None:
        monkeypatch.setenv("GIT_AI_COMMIT_BACKEND", env)
    config = {} if configured is None else {"backend": configured}

    assert resolve_backend(config, override) == expected


def test_unknown_backend_lists_valid_names() -> None:
    with pytest.raises(ValueError, match="Unknown backend 'nope'. Use one of: api, command"):
        resolve_backend({"backend": "nope"})


def test_api_backend_requires_key_only_when_used(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is not set"):
        build_backend({"api": {"provider": "openai", "model": "gpt-6-luna"}}, "api")
    assert isinstance(
        build_backend({"command": {"argv": ["claude", "-p"]}}, "command"),
        CommandBackend,
    )


def test_unsupported_api_provider_has_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(ValueError, match="Unsupported api.provider 'gemini'. Supported: openai"):
        ApiBackend({"provider": "gemini", "model": "x"})


def test_command_config_merges_across_files(tmp_path, monkeypatch) -> None:
    config = load_config(
        tmp_path,
        monkeypatch,
        global_yaml="command:\n  timeout_seconds: 15\n",
        project_yaml="backend: command\ncommand:\n  argv: [claude, -p]\n",
    )

    command = build_backend(config, resolve_backend(config))
    assert command == CommandBackend(argv=("claude", "-p"), timeout_seconds=15)


def test_main_generates_with_command_backend(
    fake_cli, tmp_path, monkeypatch, capsys
) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text(
        "backend: command\ncommand:\n  argv: [fake-cli]\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("FAKE_REPLY", "```\nfeat: add app\n```")
    monkeypatch.chdir(repo)

    assert main([]) == 0

    assert capsys.readouterr().out.strip() == "feat: add app"
    assert "diff --git a/app.py b/app.py" in json.loads(fake_cli.read_text())["stdin"]


def test_backend_flag_overrides_config(fake_cli, tmp_path, monkeypatch, capsys) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text("command:\n  argv: [fake-cli]\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(repo)

    assert main(["--backend", "command"]) == 0
    assert capsys.readouterr().out.strip() == "feat: add thing"


def test_command_errors_are_reported(tmp_path, monkeypatch, capsys) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text(
        "backend: command\ncommand:\n  argv: [nope-cli]\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(repo)

    assert main([]) == 1
    assert "Error: command 'nope-cli' not found on PATH" in capsys.readouterr().err


def test_invalid_backend_flag_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["--backend", "nope"])


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
async def test_interrupting_generation_kills_command(
    signum, fake_cli, tmp_path, monkeypatch
) -> None:
    repo = make_repo(tmp_path)
    (repo / ".git-ai-commit.yaml").write_text(
        "backend: command\ncommand:\n  argv: [fake-cli]\n"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKE_SLEEP", "30")
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    record = await wait_for_record(fake_cli)

    process.send_signal(signum)
    process.wait(timeout=10)

    await wait_until_dead(record["pid"])
    assert process.returncode != 0
```

Also add `import json` to the top of the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_ai_commit_backends.py -v`
Expected: `ImportError: cannot import name 'ApiBackend'`.

- [ ] **Step 3: Add selection and `ApiBackend` to the backends module**

In `src/git_ai_commit_backends.py`, extend the imports:

```python
from typing import Any, Protocol

from openai import AsyncOpenAI

from git_ai_commit_models import model_parameters
```

Add below the imports:

```python
BACKEND_ENV_VAR = "GIT_AI_COMMIT_BACKEND"
VALID_BACKENDS = ("api", "command")
SUPPORTED_API_PROVIDERS = ("openai",)


class Backend(Protocol):
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str: ...


def resolve_backend(config: dict[str, Any], override: str | None = None) -> str:
    """Pick the backend: CLI flag, then environment, then config, then ``api``."""
    name = override or os.getenv(BACKEND_ENV_VAR) or config.get("backend") or "api"
    if not isinstance(name, str) or name.strip().lower() not in VALID_BACKENDS:
        raise ValueError(
            f"Unknown backend {name!r}. Use one of: {', '.join(VALID_BACKENDS)}."
        )
    return name.strip().lower()


def build_backend(config: dict[str, Any], name: str) -> Backend:
    if name == "command":
        return CommandBackend.from_config(config.get("command") or {})
    return ApiBackend(config["api"])


class ApiBackend:
    """Call the configured API provider with Chat Completions."""

    def __init__(
        self, config: dict[str, Any], *, client: AsyncOpenAI | None = None
    ) -> None:
        provider = config.get("provider", "openai")
        if provider not in SUPPORTED_API_PROVIDERS:
            raise ValueError(
                f"Unsupported api.provider {provider!r}. "
                f"Supported: {', '.join(SUPPORTED_API_PROVIDERS)}."
            )
        if client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            client = AsyncOpenAI(api_key=api_key)
        self.config = config
        self.client = client

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        api_params: dict[str, Any] = {
            **model_parameters(self.config),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = await self.client.chat.completions.create(**api_params)
        return response.choices[0].message.content or ""
```

`build_backend` references `CommandBackend`, defined later in the same module; that is fine at call time.

- [ ] **Step 4: Wire the backend into `GitAICommit`**

In `src/git_ai_commit.py`:

1. Imports: add `import argparse` and `import signal` to the stdlib block; delete `from openai import AsyncOpenAI` and `from git_ai_commit_models import model_parameters`; change the backends import to:

```python
from git_ai_commit_backends import (
    VALID_BACKENDS,
    build_backend,
    clean_output,
    normalize_legacy_config,
    resolve_backend,
)
```

2. Replace the first five lines of `__init__` (`:188-193`) with:

```python
    def __init__(self, *, backend: Optional[str] = None):
        self.config = self._load_config()
        self.backend = build_backend(
            self.config, resolve_backend(self.config, backend)
        )
```

3. In `generate_suggestion`, replace everything from `# Build API parameters` through `suggestion = clean_output(response.choices[0].message.content or "")` with:

```python
            suggestion = clean_output(
                await self.backend.complete(
                    system_prompt=system_prompt, user_prompt=user_prompt
                )
            )
```

Update its docstring line `Generate a commit message suggestion using AI.` to `Generate a commit message suggestion with the configured backend.`

4. Replace `main()` (`:1198-1206`) with:

```python
def _raise_keyboard_interrupt(signum, frame) -> None:
    raise KeyboardInterrupt


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="git-ai-commit",
        description="Generate a commit message for the staged changes.",
    )
    parser.add_argument(
        "--backend",
        choices=VALID_BACKENDS,
        help="override the configured backend for this run",
    )
    args = parser.parse_args(argv)
    # SIGTERM takes the same cleanup path as Ctrl+C, so the command is killed.
    previous_handler = signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)

    try:
        committer = GitAICommit(backend=args.backend)
        suggestion = asyncio.run(committer.generate_suggestion())
        return 0 if suggestion else 1
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print_output(f"Error: {str(e)}", is_error=True)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
```

Leave `if __name__ == "__main__": exit(main())` unchanged.

- [ ] **Step 5: Add `backend` and `command` to the default config**

In `config/default_config.yaml`, insert above `# API backend settings`:

```yaml
# Backend: where commit messages come from
#   api     - call an API provider directly (default)
#   command - run a local CLI such as claude, codex, cursor-agent or ollama
# Override per shell with GIT_AI_COMMIT_BACKEND, or per run with --backend.
backend: api

# Command backend settings (used when backend: command)
# argv is run directly, never through a shell. Placeholders:
#   {prompt}         prompt as an argument (otherwise sent on stdin)
#   {system_prompt}  system prompt as an argument (otherwise prepended to the prompt)
#   {output_file}    temp file the CLI writes its answer to (otherwise stdout is read)
# See README.md "Local CLI Backends" for ready-made recipes.
command:
  # argv: ["claude", "-p", "--output-format", "text", "--model", "haiku"]
  timeout_seconds: 60
```

- [ ] **Step 6: Update the existing model tests to the backend object**

In `tests/test_git_ai_commit_models.py`:

1. Add `from git_ai_commit_backends import ApiBackend` to the imports.
2. In `make_committer`, replace

```python
    committer.client = SimpleNamespace(
```
with
```python
    client = SimpleNamespace(
```
and add after that statement's closing parenthesis:
```python
    committer.backend = ApiBackend(committer.config["api"], client=client)
```
3. Replace every `committer.client.chat` with `committer.backend.client.chat` (in the test bodies and in `test_generated_message_is_cleaned` from Task 2).
4. In `test_real_sdk_serializes_compatible_request`, replace `committer.client = client` with `committer.backend = ApiBackend(committer.config["api"], client=client)`.

- [ ] **Step 7: Run the full suite and linters**

Run: `uv run pytest -q && uv run black src/ tests/ && uv run ruff check src/ && uv run mypy src/`
Expected: all pass. `tests/test_packaging.py` still sees `OPENAI_API_KEY environment variable is not set` because the default backend is `api`.

- [ ] **Step 8: Commit**

```bash
git add config/default_config.yaml src/ tests/
git commit -m "feat: select api or command backend from config, env or flag"
```

---

### Task 5: Shell integration and documentation

**Files:**
- Modify: `git-ai-commit.plugin.zsh:136` (`_git_ai_commit_loading`)
- Modify: `bin/lazygit-generate-commit.sh:13`
- Modify: `README.md` (Prerequisites, Installation step 5, Configuration block, new section before `## Usage`)
- Modify: `CLAUDE.md` (Project Overview, Architecture, Configuration System, Model Compatibility)

**Interfaces:**
- Consumes: `GIT_AI_COMMIT_BACKEND` env var and config keys from Task 4.
- Produces: user-facing docs only.

- [ ] **Step 1: Show the backend in the loading text**

In `git-ai-commit.plugin.zsh:136`, change

```zsh
    local base_msg="🤖 Generating commit message"
```
to
```zsh
    local base_msg="🤖 Generating commit message${GIT_AI_COMMIT_BACKEND:+ (${GIT_AI_COMMIT_BACKEND})}"
```

- [ ] **Step 2: Verify the zsh change manually**

Run: `zsh -n git-ai-commit.plugin.zsh` → expected: no output (syntax OK).
Then in a new shell with the plugin loaded, inside a repo with staged changes: `export GIT_AI_COMMIT_BACKEND=command`, type `git commit -m ` and press TAB → expected: status line reads `🤖 Generating commit message (command)...`. Press Ctrl+C during generation and run `pgrep -fl <your cli>` → expected: no leftover process.

- [ ] **Step 3: Update the lazygit header**

In `bin/lazygit-generate-commit.sh:13`, change `#   - OPENAI_API_KEY environment variable set` to `#   - OPENAI_API_KEY set (api backend) or a configured command backend`.

- [ ] **Step 4: Update the README**

1. Prerequisites: change `- OpenAI API key` to `- OpenAI API key, or a local AI CLI (Claude Code, Codex, Cursor Agent, Ollama, …)`.
2. Installation step 5: change the heading line to `5. Set your OpenAI API key in your \`.zshrc\` (skip if you only use a local CLI):`.
3. Configuration block: replace `# OpenAI API settings` / `openai:` with:

```yaml
# Where messages come from: api (default) or command
backend: api

# API backend settings
api:
  provider: openai
```

keeping the `model`, `reasoning_effort`, `temperature`, `max_tokens` lines underneath. Below the block add: `Older configs with a top-level \`openai:\` section keep working; they are read as \`api:\`.`

4. Insert this section immediately before `## Usage`:

````markdown
## Local CLI Backends

Instead of calling the OpenAI API, git-ai-commit can run any local AI CLI you already use. Set `backend: command` and describe the command:

```yaml
backend: command
command:
  argv: ["claude", "-p", "--output-format", "text", "--model", "haiku"]
  timeout_seconds: 60
```

`argv` runs directly, never through a shell, in an empty temporary directory. All repository context is already in the prompt, so the CLI does not need to read your files.

| Placeholder | Meaning | If absent |
|---|---|---|
| `{prompt}` | Prompt as an argument | Prompt is sent on stdin (recommended: large diffs can exceed argument limits) |
| `{system_prompt}` | System prompt as an argument | System prompt is prepended to the prompt |
| `{output_file}` | Temp file the CLI writes its answer to | stdout is read |

Switch backends without editing config:

```bash
export GIT_AI_COMMIT_BACKEND=command   # this shell
git-ai-commit --backend api            # one manual run
```

Precedence: `--backend` > `GIT_AI_COMMIT_BACKEND` > project config > global config > `api`. `OPENAI_API_KEY` is only needed for the `api` backend.

Local CLIs start slower than an API call (often several seconds) and do not use OpenAI prompt caching. Pick a small, fast model. On timeout or Ctrl+C the CLI and any processes it started are stopped.

### Recipes

Flags change between releases; check `<tool> --help` if a recipe stops working.

**Claude Code** (tools disabled, system prompt passed separately):

```yaml
command:
  argv: ["claude", "-p", "--output-format", "text", "--model", "haiku",
         "--tools", "", "--system-prompt", "{system_prompt}"]
```

**Codex** (read-only sandbox, answer read from a file):

```yaml
command:
  argv: ["codex", "exec", "-m", "gpt-5.4-mini", "-s", "read-only",
         "--skip-git-repo-check", "-o", "{output_file}", "-"]
```

**Cursor Agent**:

```yaml
command:
  argv: ["cursor-agent", "-p", "--output-format", "text", "--model", "auto",
         "{prompt}"]
```

**Ollama** (fully local):

```yaml
command:
  argv: ["ollama", "run", "--hidethinking", "qwen3:8b"]
  timeout_seconds: 120
```
````

- [ ] **Step 5: Verify each recipe against the installed CLIs**

For each of `claude`, `codex`, `ollama` that is installed, put its recipe in a scratch `.git-ai-commit.yaml` inside a test repo with a staged change and run `uv run --project <plugin-dir> git-ai-commit`. Expected: a single commit message on stdout, nothing else. If a flag is rejected, fix the recipe using `<tool> --help`. `cursor-agent` is not installed on the author's machine: confirm its flags against the [Cursor CLI docs](https://cursor.com/docs/cli/overview) and keep the `{prompt}` form unless the docs confirm stdin input in print mode.

- [ ] **Step 6: Update CLAUDE.md**

- Project Overview, **Tech Stack** line: `Python 3.11+ (core logic) + Zsh (shell integration) + OpenAI API or a local AI CLI`.
- Architecture → Python Layer bullet `Calls OpenAI Chat Completions without streaming` → `Sends the prompts to a backend: the OpenAI API (non-streaming Chat Completions) or a user-configured local CLI`.
- Add under **Key Python Components**:

```markdown
**Backends** (src/git_ai_commit_backends.py):

- `resolve_backend()`: `--backend` > `GIT_AI_COMMIT_BACKEND` > project > global > `api`
- `ApiBackend`: OpenAI Chat Completions; the only place `OPENAI_API_KEY` is required
- `CommandBackend`: runs `command.argv` without a shell in an empty temp dir, own process group; `{prompt}`, `{system_prompt}`, `{output_file}` placeholders, stdin/stdout by default; kills the group on timeout, Ctrl+C or SIGTERM
- `normalize_legacy_config()`: maps a top-level `openai:` block to `api:` per config file
- `clean_output()`: strips preamble lines, code fences and wrapping quotes for both backends
```

- Configuration System → Key config sections: replace the `openai` bullet with
  - `` `backend`: `api` (default) or `command` ``
  - `` `api`: `provider` (only `openai`), model (default `gpt-6-luna`), automatically normalized `reasoning_effort`, temperature, max_tokens. Legacy top-level `openai:` is read as `api:` ``
  - `` `command`: `argv` and `timeout_seconds` (default 60) ``
- Model Compatibility, packaging bullet: `exposes the two top-level modules` → `exposes the three top-level modules (git_ai_commit, git_ai_commit_models, git_ai_commit_backends)`.

- [ ] **Step 7: Run the full suite one last time**

Run: `uv run pytest -q && uv run ruff check src/ && uv run mypy src/`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add git-ai-commit.plugin.zsh bin/lazygit-generate-commit.sh README.md CLAUDE.md
git commit -m "docs: document local cli backends with recipes"
```
