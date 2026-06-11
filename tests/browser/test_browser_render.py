import pytest

from agent_env_core.browser.render import _launch_options, browser_navigate_and_render


async def _chromium_available():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return False
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            await browser.close()
        return True
    except Exception:
        return False


@pytest.mark.browser
def test_debug_headed_launch_option(monkeypatch):
    monkeypatch.setenv("DEBUG_HEADED", "1")
    assert _launch_options() == {"headless": False}
    monkeypatch.delenv("DEBUG_HEADED")
    assert _launch_options() == {"headless": True}


@pytest.mark.browser
@pytest.mark.asyncio
async def test_invalid_url_returns_structured_error(response_schema):
    response = await browser_navigate_and_render("file:///tmp/nope")
    response_schema(response)
    assert not response["success"]
    assert response["domain"] == "browser"


@pytest.mark.browser
@pytest.mark.asyncio
async def test_data_url_render_when_chromium_available(response_schema):
    if not await _chromium_available():
        pytest.skip("Playwright Chromium browser binary is not available")
    response = await browser_navigate_and_render(
        "data:text/html,<title>T</title><body>Hello browser</body>"
    )
    response_schema(response)
    assert response["success"]
    assert "Hello browser" in response["data"]["text_content"]
    assert response["data"]["wait_until"] == "networkidle"
    assert response["data"]["screenshot_width"] <= 1280
    assert response["visual_state"]
