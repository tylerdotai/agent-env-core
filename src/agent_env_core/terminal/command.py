"""Async terminal command tool."""

import asyncio
import shlex
import time
from typing import Any

from agent_env_core.exceptions import (
    ActionFailedError,
    CommandParseError,
    InteractivePromptException,
    TimeoutExceededError,
)
from agent_env_core.response import Response, make_response
from agent_env_core.timing import Timer

from .env import build_subprocess_env
from .safety import assert_safe_command
from .stream import collect_streams


def parse_command(command: str) -> list[str]:
    """Parse a command string into argv without invoking a shell."""
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise CommandParseError(
            str(exc), "Pass a valid command string with balanced quotes."
        ) from exc
    if not argv:
        raise CommandParseError("Command must not be empty.", "Pass an executable and arguments.")
    return argv


async def terminal_execute_command(command: str, timeout_sec: int = 30) -> Response:
    """Execute a command asynchronously without a shell and return the shared schema.

    Args:
        command: Command string parsed with POSIX-style quoting into argv. Shell pipelines,
            redirects, glob expansion, aliases, and built-ins are not interpreted.
        timeout_sec: Maximum runtime in seconds. Values above 300 are rejected.

    Returns:
        A dict with the package response envelope. `data` includes the original command, argv,
        exit code, stdout, stderr, truncation flags, timeout flag, and duration.

    Failure behavior:
        Parse errors, refused destructive commands, interactive prompts, timeouts, launch failures,
        and non-zero exits are returned as structured errors instead of escaping.
    """
    timer = Timer()
    base_data: dict[str, Any] = {
        "command": command,
        "argv": [],
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "timed_out": False,
        "duration_ms": 0,
    }
    try:
        if timeout_sec > 300:
            raise TimeoutExceededError(
                "timeout_sec must be less than or equal to 300.",
                "Use a timeout no greater than 300 seconds.",
            )
        if timeout_sec <= 0:
            raise TimeoutExceededError("timeout_sec must be positive.", "Use a positive timeout.")
        argv = parse_command(command)
        base_data["argv"] = argv
        assert_safe_command(argv)
        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=build_subprocess_env(),
        )
        assert process.stdout is not None
        assert process.stderr is not None
        try:
            stdout, stderr, out_trunc, err_trunc = await asyncio.wait_for(
                collect_streams(process.stdout, process.stderr), timeout=timeout_sec
            )
            remaining = max(0.001, timeout_sec - (time.monotonic() - start))
            exit_code = await asyncio.wait_for(process.wait(), timeout=remaining)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            base_data.update({"timed_out": True, "duration_ms": timer.elapsed_ms()})
            raise TimeoutExceededError(
                "Command timed out.", "Increase timeout_sec or run a faster command."
            ) from exc
        except InteractivePromptException:
            process.kill()
            await process.wait()
            raise
        base_data.update(
            {
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": out_trunc,
                "stderr_truncated": err_trunc,
                "duration_ms": timer.elapsed_ms(),
            }
        )
        if exit_code != 0:
            raise ActionFailedError(
                f"Command exited with status {exit_code}.",
                "Inspect stdout and stderr for the command failure reason.",
            )
        return make_response(
            success=True,
            execution_time_ms=timer.elapsed_ms(),
            domain="terminal",
            tool_name="terminal_execute_command",
            data=base_data,
        )
    except Exception as exc:
        base_data["duration_ms"] = timer.elapsed_ms()
        return make_response(
            success=False,
            execution_time_ms=timer.elapsed_ms(),
            domain="terminal",
            tool_name="terminal_execute_command",
            data=base_data,
            error=exc,
        )
