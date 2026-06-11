import shlex
import sys

import pytest

from agent_env_core.terminal.command import terminal_execute_command


def pycmd(code):
    return f"{sys.executable} -c {shlex.quote(code)}"


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_interactive_prompt_returns_structured_error():
    response = await terminal_execute_command(pycmd("print('password:')"))
    assert not response["success"]
    assert response["error"]["type"] == "InteractivePromptException"
