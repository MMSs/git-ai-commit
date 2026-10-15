"""Select and run the backend that turns prompts into a commit message."""

import asyncio
import contextlib
import os
import re
import shutil
import signal
import tempfile
from dataclasses import dataclass
from pathlib import Path
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
        # Resolve first: an unreadable PATH entry makes exec report EACCES, not ENOENT.
        executable = shutil.which(name)
        if executable is None:
            if os.sep in name and Path(name).exists():
                raise BackendError(f"command '{name}' is not executable")
            raise BackendError(f"command '{name}' not found on PATH")
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *argv[1:],
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
