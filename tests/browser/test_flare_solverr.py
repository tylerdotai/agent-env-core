"""Tests for the FlareSolverr async client.

These tests use httpx.MockTransport to fake the FlareSolverr HTTP API —
no actual FlareSolverr container is required. Integration tests against
a real FlareSolverr instance live in tests/integration/ and are
skipped by default.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from agent_env_core.browser.flare_solverr import (
    FlareSolverrClient,
    FlareSolverrCookie,
    FlareSolverrError,
    FlareSolverrSolution,
)
from agent_env_core.exceptions import TimeoutExceededError

# Note: we deliberately do NOT use a module-level `pytestmark =
# pytest.mark.flare_solverr` here because pytest evaluates module-level
# marks before reading pyproject.toml's markers, producing a
# `PytestUnknownMarkWarning`. Per-test markers avoid that.


def _mock_transport(handler):
    """Wrap an async handler function as an httpx.MockTransport."""
    return httpx.MockTransport(handler)


def _ok_response(solution: dict) -> httpx.Response:
    return httpx.Response(200, json={"status": "ok", "message": "", "solution": solution})


def _error_response(message: str) -> httpx.Response:
    return httpx.Response(200, json={"status": "error", "message": message})


def test_solve_parses_cookies_and_user_agent():
    solution_payload = {
        "url": "https://example.com/real",
        "status": 200,
        "userAgent": "Mozilla/5.0 (Test) Chrome/120.0",
        "cookies": [
            {
                "name": "cf_clearance",
                "value": "abc123",
                "domain": ".example.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
                "expires": 1900000000,
            },
            {"name": "session", "value": "xyz", "domain": ".example.com"},
        ],
        "headers": {"content-type": "text/html"},
    }
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content)
        return _ok_response(solution_payload)

    transport = _mock_transport(handler)
    client = FlareSolverrClient(base_url="http://fake:8191")
    client._http = httpx.AsyncClient(base_url="http://fake:8191", transport=transport)

    async def run() -> FlareSolverrSolution:
        return await client.solve("https://example.com")

    sol = _run_async(run())
    assert sol.url == "https://example.com/real"
    assert sol.status == 200
    assert sol.user_agent == "Mozilla/5.0 (Test) Chrome/120.0"
    assert len(sol.cookies) == 2
    cf, sess = sol.cookies
    assert cf.name == "cf_clearance"
    assert cf.value == "abc123"
    assert cf.http_only is True
    assert cf.secure is True
    assert cf.same_site == "Lax"
    assert cf.expires == 1900000000
    assert sess.name == "session"
    assert sess.path == "/"
    # Verify the request was shaped correctly
    assert captured["url"] == "http://fake:8191/v1"
    assert captured["json"]["cmd"] == "request.get"
    assert captured["json"]["url"] == "https://example.com"
    assert captured["json"]["maxTimeout"] == 60_000
    # Verify to_playwright_cookies emits the right shape
    pw_cookies = sol.to_playwright_cookies()
    assert pw_cookies[0]["name"] == "cf_clearance"
    assert pw_cookies[0]["httpOnly"] is True
    assert pw_cookies[0]["sameSite"] == "Lax"
    assert "expires" in pw_cookies[0]


def test_solve_raises_on_error_status():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _error_response("Challenge failed: timeout")

    client = FlareSolverrClient(base_url="http://fake:8191")
    client._http = httpx.AsyncClient(
        base_url="http://fake:8191", transport=_mock_transport(handler)
    )

    async def run() -> None:
        await client.solve("https://protected.example.com")

    with pytest.raises(FlareSolverrError, match="timeout"):
        _run_async(run())


def test_solve_raises_on_connection_error():
    """A ConnectError should produce a clear FlareSolverrError with recovery hint."""
    client = FlareSolverrClient(base_url="http://nonexistent:9999")
    client._http = httpx.AsyncClient(
        base_url="http://nonexistent:9999",
        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("nope"))),
    )

    async def run() -> None:
        await client.solve("https://x")

    with pytest.raises(FlareSolverrError) as excinfo:
        _run_async(run())
    assert "docker compose up" in (excinfo.value.recovery_suggestion or "")


def test_solve_raises_timeout_on_slow_response():
    """If httpx times out, we raise TimeoutExceededError with recovery hint."""
    client = FlareSolverrClient(base_url="http://fake:8191", timeout_sec=0.001)
    client._http = httpx.AsyncClient(
        base_url="http://fake:8191",
        timeout=0.001,
        transport=httpx.MockTransport(
            lambda r: (_ for _ in ()).throw(httpx.TimeoutException("slow"))
        ),
    )

    async def run() -> None:
        await client.solve("https://x")

    with pytest.raises(TimeoutExceededError) as excinfo:
        _run_async(run())
    assert "FLARESOLVERR_HTTP_TIMEOUT" in (excinfo.value.recovery_suggestion or "")


def test_solve_uses_session_when_provided():
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return _ok_response(
            {"url": "https://x", "status": 200, "userAgent": "ua", "cookies": [], "headers": {}}
        )

    client = FlareSolverrClient(base_url="http://fake:8191", session="sticky-1")
    client._http = httpx.AsyncClient(
        base_url="http://fake:8191", transport=_mock_transport(handler)
    )

    async def run() -> None:
        await client.solve("https://x")

    _run_async(run())
    assert captured["json"]["session"] == "sticky-1"


def test_cookie_to_playwright_handles_missing_optional_fields():
    c = FlareSolverrCookie(name="a", value="b", domain="x.com")
    pw = c.to_playwright_dict("https://x.com")
    assert pw["name"] == "a"
    assert pw["value"] == "b"
    assert pw["domain"] == "x.com"
    assert pw["path"] == "/"
    assert pw["httpOnly"] is False
    assert pw["secure"] is False
    assert "sameSite" not in pw
    assert "expires" not in pw


def test_cookie_to_playwright_drops_invalid_same_site():
    c = FlareSolverrCookie(name="a", value="b", domain="x.com", same_site="bogus")
    pw = c.to_playwright_dict("https://x.com")
    assert "sameSite" not in pw


def test_require_httpx_succeeds_when_installed():
    # httpx is installed in our test env (it's a transitive dep of pytest
    # for the async test runner on this project)
    from agent_env_core.browser.flare_solverr import require_httpx

    require_httpx()  # should not raise


# ----------------------------------------------------------------------
# Test helpers
# ----------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine to completion using asyncio.run.

    We can't use pytest-asyncio's @pytest.mark.asyncio decorator here
    without confusing the pytest runner's import hooks. A simple helper
    is the cleanest approach.
    """
    import asyncio

    return asyncio.run(coro)


# ----------------------------------------------------------------------
# Live integration test
# ----------------------------------------------------------------------
# This test is opt-in via the FLARESOLVERR_LIVE_TEST=1 env var. When set,
# it requires a real FlareSolverr container reachable at FLARESOLVERR_URL
# (defaults to http://localhost:8191). It exercises the *real* Cloudflare
# bypass against https://nowsecure.nl — this is the production code path,
# not a mocked one. CI runs this in the flaresolverr-integration job.

LIVE_TEST = os.environ.get("FLARESOLVERR_LIVE_TEST") == "1"


@pytest.mark.skipif(
    not LIVE_TEST,
    reason="set FLARESOLVERR_LIVE_TEST=1 to run; requires a real FlareSolverr container",
)
def test_live_bypass_against_nowsecure_nl() -> None:
    base_url = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191")
    timeout_sec = float(os.environ.get("FLARESOLVERR_TIMEOUT_SEC", "90"))

    async def _run() -> None:
        async with FlareSolverrClient(base_url=base_url, timeout_sec=timeout_sec) as client:
            sol = await client.solve("https://nowsecure.nl")
        assert sol.status == 200, f"expected 200, got {sol.status}"
        assert sol.url, "no final url"
        assert sol.user_agent, "no user agent"
        cf_cookie = next((c for c in sol.cookies if c.name == "cf_clearance"), None)
        assert cf_cookie is not None, f"no cf_clearance in {len(sol.cookies)} cookies"
        assert len(cf_cookie.value) > 50, "cf_clearance value suspiciously short"
        # The Playwright cookie shape must be valid.
        pw_cookies = sol.to_playwright_cookies()
        assert pw_cookies, "no playwright cookies produced"
        for c in pw_cookies:
            assert "name" in c and "value" in c and "domain" in c

    _run_async(_run())
