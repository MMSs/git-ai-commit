"""Verify the command backend runs local CLIs safely."""

import asyncio
import json
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
