"""Async browser navigate and render tool."""

import os
from typing import Literal
from urllib.parse import urlparse

from agent_env_core.exceptions import (
    ActionFailedError,
    DependencyMissingError,
    TimeoutExceededError,
)
from agent_env_core.response import Response, make_response
from agent_env_core.timing import Timer

from .flare_solverr import FlareSolverrClient, FlareSolverrError
from .screenshot import screenshot_png_to_jpeg_base64

WAIT_UNTIL: Literal["networkidle"] = "networkidle"


def _launch_options() -> dict[str, bool]:
    return {"headless": os.environ.get("DEBUG_HEADED") != "1"}


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "data"}:
        raise ActionFailedError("URL must use http, https, or data scheme.", "Pass a browser URL.")


def _flaresolverr_enabled() -> bool:
    """Return True if the agent has opted into automatic Cloudflare bypass."""
    return os.environ.get("FLARESOLVERR_AUTO_BYPASS", "0") == "1"


async def browser_navigate_and_render(url: str) -> Response:
    """Navigate Chromium to a URL, capture text and a JPEG screenshot, and return the schema.

    Args:
        url: `http`, `https`, or `data` URL to load in a fresh Chromium page.

    Returns:
        A dict with the shared response envelope. `data` includes requested/final URL, title,
        text content, viewport dimensions, screenshot dimensions/format, and wait strategy.
        `visual_state` is a base64 JPEG screenshot downsampled to at most 1280px wide.
        If `FLARESOLVERR_AUTO_BYPASS=1` is set, Cloudflare/DDoS-GUARD challenges are
        automatically solved via FlareSolverr and the cleared cookies are injected into
        the browser context.

    Failure behavior:
        Missing Playwright/Pillow dependencies, invalid URLs, navigation failures, and timeouts are
        caught and returned as structured errors. Install `agent-env-core[browser]` and Playwright
        browser binaries before using this tool. FlareSolverr requires the `[flare-solverr]`
        extra and a running FlareSolverr container (see references/flare-solverr.md).
    """
    timer = Timer()
    try:
        _validate_url(url)
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise DependencyMissingError(
                "Playwright is required for browser rendering.",
                "Install agent-env-core[browser] and run `python -m playwright install chromium`.",
            ) from exc
        flaresolverr_solution = None
        if _flaresolverr_enabled():
            try:
                async with FlareSolverrClient() as fs_client:
                    flaresolverr_solution = await fs_client.solve(url)
            except (FlareSolverrError, TimeoutExceededError):
                # Surface the failure; do not silently fall back to a bare
                # navigation (that would just hit the wall again).
                raise
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=_launch_options()["headless"])
            try:
                if flaresolverr_solution is not None:
                    context = await browser.new_context(
                        user_agent=flaresolverr_solution.user_agent or None,
                    )
                    if flaresolverr_solution.cookies:
                        playwright_cookies = flaresolverr_solution.to_playwright_cookies()
                        await context.add_cookies(playwright_cookies)  # type: ignore[arg-type]
                    page = await context.new_page()
                else:
                    page = await browser.new_page()
                try:
                    await page.goto(url, wait_until=WAIT_UNTIL)
                    title = await page.title()
                    text = await page.locator("body").inner_text()
                    viewport = page.viewport_size or {"width": 0, "height": 0}
                    png = await page.screenshot(type="png")
                    final_url = page.url
                except PlaywrightTimeoutError as exc:
                    raise TimeoutExceededError(
                        "Browser navigation timed out.", "Try a faster URL."
                    ) from exc
            finally:
                await browser.close()
        visual, width, height, fmt = screenshot_png_to_jpeg_base64(png)
        data = {
            "requested_url": url,
            "final_url": final_url,
            "title": title,
            "text_content": text,
            "viewport_width": viewport["width"],
            "viewport_height": viewport["height"],
            "screenshot_width": width,
            "screenshot_height": height,
            "screenshot_format": fmt,
            "wait_until": WAIT_UNTIL,
        }
        return make_response(
            success=True,
            execution_time_ms=timer.elapsed_ms(),
            domain="browser",
            tool_name="browser_navigate_and_render",
            data=data,
            visual_state=visual,
        )
    except Exception as exc:
        return make_response(
            success=False,
            execution_time_ms=timer.elapsed_ms(),
            domain="browser",
            tool_name="browser_navigate_and_render",
            error=exc,
        )
