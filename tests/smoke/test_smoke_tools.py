import shlex
import sys

import pytest

import agent_env_core
from agent_env_core.desktop import capture


def pycmd(code):
    return f"{sys.executable} -c {shlex.quote(code)}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_terminal_smoke(response_schema):
    response = await agent_env_core.terminal_execute_command(pycmd("print('smoke')"))
    response_schema(response)
    assert response["success"]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_browser_smoke_skips_without_chromium(response_schema):
    try:
        from tests.browser.test_browser_render import _chromium_available
    except Exception:
        pytest.skip("Playwright is not importable")
    if not await _chromium_available():
        pytest.skip("Playwright Chromium browser binary is not available")
    response = await agent_env_core.browser_navigate_and_render("data:text/html,<body>smoke</body>")
    response_schema(response)
    assert response["success"]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_desktop_smoke_with_mock_backend(monkeypatch, png_bytes, response_schema):
    class FakeBackend:
        name = "smoke-fake"

        def capture_screen(self):
            return png_bytes

        def screen_size(self):
            return (40, 40)

    monkeypatch.setattr(capture, "get_desktop_backend", lambda: FakeBackend())
    monkeypatch.setattr(capture, "display_server", lambda: "test-display")
    response = await agent_env_core.desktop_capture_and_locate()
    response_schema(response)
    assert response["success"]
