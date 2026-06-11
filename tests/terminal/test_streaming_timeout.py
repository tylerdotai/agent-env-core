import shlex
import sys

import pytest

from agent_env_core.terminal.command import terminal_execute_command


def pycmd(code):
    return f"{sys.executable} -c {shlex.quote(code)}"


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_timeout_kills_process():
    response = await terminal_execute_command(pycmd("import time; time.sleep(2)"), timeout_sec=1)
    assert not response["success"]
    assert response["error"]["type"] == "TimeoutError"
    assert response["data"]["timed_out"]


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_timeout_above_max_rejected():
    response = await terminal_execute_command(pycmd("print(1)"), timeout_sec=301)
    assert not response["success"]
    assert response["error"]["type"] == "TimeoutError"


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_stream_truncation_flag_set():
    response = await terminal_execute_command(pycmd("print('a'*10050)"))
    assert response["success"]
    assert len(response["data"]["stdout"]) == 10000
    assert response["data"]["stdout_truncated"]


@pytest.mark.terminal
@pytest.mark.asyncio
async def test_stdout_and_stderr_are_collected():
    response = await terminal_execute_command(
        pycmd("import sys; print('out'); print('err', file=sys.stderr)")
    )
    assert response["success"]
    assert "out" in response["data"]["stdout"]
    assert "err" in response["data"]["stderr"]
