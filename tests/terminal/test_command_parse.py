import shlex
import sys

import pytest

from agent_env_core.terminal.command import parse_command, terminal_execute_command


def pycmd(code):
    return f"{sys.executable} -c {shlex.quote(code)}"


@pytest.mark.terminal
def test_shell_features_are_not_implicitly_executed():
    assert parse_command("echo hello | wc") == ["echo", "hello", "|", "wc"]


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_empty_command_returns_parse_error(response_schema):
    response = await terminal_execute_command("")
    response_schema(response)
    assert not response["success"]
    assert response["error"]["type"] == "CommandParseError"


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_parsed_argv_recorded_for_safe_command():
    response = await terminal_execute_command(pycmd("print(123)"))
    assert response["success"]
    assert response["data"]["argv"][:2] == [sys.executable, "-c"]
    assert response["data"]["stdout"].strip() == "123"


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_nonzero_exit_preserves_output():
    response = await terminal_execute_command(pycmd("import sys; print('x'); sys.exit(3)"))
    assert not response["success"]
    assert response["error"]["type"] == "ActionFailed"
    assert response["data"]["stdout"].strip() == "x"
    assert response["data"]["exit_code"] == 3
