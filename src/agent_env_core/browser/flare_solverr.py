"""Async client for the FlareSolverr HTTP API.

FlareSolverr (https://github.com/FlareSolverr/FlareSolverr) is a small
self-hosted proxy that solves Cloudflare and DDoS-GUARD challenges using
Selenium + undetected-chromedriver. It exposes a simple JSON-over-HTTP
API on port 8191 by default. This client wraps that API and returns
the solved cookies + user-agent that the agent can inject into a
Playwright session to bypass the challenge.

Reference: https://github.com/FlareSolverr/FlareSolverr#usage
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, cast

import httpx

from ..exceptions import (
    AgentEnvCoreError,
    DependencyMissingError,
    TimeoutExceededError,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8191"
DEFAULT_TIMEOUT_MS = 60_000
DEFAULT_HTTP_TIMEOUT_SEC = 90.0  # Must be > maxTimeout + FlareSolverr startup


class FlareSolverrError(AgentEnvCoreError):
    """Raised when FlareSolverr returns an error response or is unreachable."""


@dataclass(frozen=True)
class FlareSolverrCookie:
    """A single cookie returned by FlareSolverr after solving a challenge.

    Compatible with Playwright's `context.add_cookies()` input shape
    (camelCase keys).
    """

    name: str
    value: str
    domain: str
    path: str = "/"
    http_only: bool = False
    secure: bool = False
    same_site: str | None = None
    expires: float = -1

    def to_playwright_dict(self, url: str) -> dict[str, Any]:
        """Return a dict suitable for `browser_context.add_cookies([...])`.

        The dict uses Playwright's snake_case keys. ``sameSite`` is mapped
        to one of Playwright's accepted values.
        """
        same_site = self.same_site
        if same_site is not None and same_site not in {"Strict", "Lax", "None"}:
            same_site = None
        cookie: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "path": self.path,
            "httpOnly": self.http_only,
            "secure": self.secure,
        }
        if same_site is not None:
            cookie["sameSite"] = same_site
        if self.expires and self.expires > 0:
            cookie["expires"] = self.expires
        return cookie


@dataclass(frozen=True)
class FlareSolverrSolution:
    """The solved result from FlareSolverr.

    Attributes:
        url: The final URL after redirects (may differ from the requested URL).
        status: HTTP status of the solved response.
        user_agent: User-Agent string the browser used; reuse this in Playwright
            so the Cloudflare fingerprint check passes.
        cookies: Cookies to inject into the Playwright context.
        headers: Response headers (rarely needed, included for completeness).
    """

    url: str
    status: int
    user_agent: str
    cookies: tuple[FlareSolverrCookie, ...]
    headers: dict[str, str] = field(default_factory=dict)

    def to_playwright_cookies(self) -> list[dict[str, Any]]:
        """Return cookies in the shape Playwright's add_cookies() expects."""
        return [c.to_playwright_dict(self.url) for c in self.cookies]


class FlareSolverrClient:
    """Thin async client for the FlareSolverr HTTP API.

    Usage:
        client = FlareSolverrClient()
        solution = await client.solve("https://example.com")
        # Pass solution.to_playwright_cookies() and solution.user_agent
        # to your Playwright browser_context.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout_sec: float | None = None,
        session: str | None = None,
    ) -> None:
        resolved_base = base_url or os.environ.get("FLARESOLVERR_URL") or DEFAULT_BASE_URL
        self._base_url = resolved_base.rstrip("/")
        self._timeout_sec = (
            timeout_sec
            if timeout_sec is not None
            else float(os.environ.get("FLARESOLVERR_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT_SEC))
        )
        self._session = session or os.environ.get("FLARESOLVERR_SESSION")
        self._owns_client = True
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> FlareSolverrClient:
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_sec,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._http is None:
            raise FlareSolverrError(
                "FlareSolverrClient must be used as an async context manager.",
                "Use 'async with FlareSolverrClient() as c:'.",
            )
        try:
            response = await self._http.post("/v1", json=payload)
        except httpx.ConnectError as exc:
            raise FlareSolverrError(
                f"Cannot reach FlareSolverr at {self._base_url}.",
                "Start the FlareSolverr container: docker compose up -d flaresolverr",
            ) from exc
        except httpx.TimeoutException as exc:
            raise TimeoutExceededError(
                f"FlareSolverr request timed out after {self._timeout_sec}s.",
                "Increase FLARESOLVERR_HTTP_TIMEOUT or check FlareSolverr health.",
            ) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FlareSolverrError(
                f"FlareSolverr returned HTTP {exc.response.status_code}.",
                "Check FlareSolverr logs: docker logs flaresolverr",
            ) from exc
        return cast("dict[str, Any]", response.json())

    async def health(self) -> bool:
        """Return True if FlareSolverr is reachable and responsive."""
        if self._http is None:
            raise FlareSolverrError(
                "FlareSolverrClient must be used as an async context manager.",
                "Use 'async with FlareSolverrClient() as c:'.",
            )
        try:
            resp = await self._http.get("/health", timeout=5.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
        if resp.status_code != 200:
            return False
        try:
            payload = cast("dict[str, Any]", resp.json())
        except Exception:  # noqa: BLE001 — defensive
            return False
        return payload.get("status") == "ok"

    async def solve(
        self,
        url: str,
        *,
        max_timeout_ms: int = DEFAULT_TIMEOUT_MS,
        session: str | None = None,
    ) -> FlareSolverrSolution:
        """Solve a Cloudflare/DDoS-GUARD challenge for ``url`` and return the result.

        Args:
            url: The target URL to solve a challenge for.
            max_timeout_ms: How long FlareSolverr should spend solving
                the challenge before giving up. Default 60s.
            session: Optional FlareSolverr session id for sticky cookies.
                If omitted, a one-shot session is used.

        Returns:
            FlareSolverrSolution with the solved cookies, user-agent, and
            final URL.

        Raises:
            FlareSolverrError: If FlareSolverr returns a non-OK status or is unreachable.
            TimeoutExceededError: If the HTTP request itself times out.
        """
        payload: dict[str, Any] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": max_timeout_ms,
        }
        session_id = session or self._session
        if session_id:
            payload["session"] = session_id

        LOGGER.info("Asking FlareSolverr to solve %s", url)
        body = await self._post(payload)
        status = body.get("status")
        message = body.get("message", "")
        if status != "ok":
            raise FlareSolverrError(
                f"FlareSolverr could not solve the challenge: {message}",
                "Increase maxTimeoutMs, retry with a fresh session, or check the target URL.",
            )
        solution = body.get("solution") or {}
        cookies_raw = solution.get("cookies") or []
        cookies = tuple(
            FlareSolverrCookie(
                name=str(c.get("name", "")),
                value=str(c.get("value", "")),
                domain=str(c.get("domain", "")),
                path=str(c.get("path", "/") or "/"),
                http_only=bool(c.get("httpOnly", False)),
                secure=bool(c.get("secure", False)),
                same_site=c.get("sameSite"),
                expires=float(c.get("expires", -1) or -1),
            )
            for c in cookies_raw
        )
        user_agent = str(solution.get("userAgent") or "")
        final_url = str(solution.get("url") or url)
        try:
            final_status = int(solution.get("status", 200))
        except (TypeError, ValueError):
            final_status = 200
        return FlareSolverrSolution(
            url=final_url,
            status=final_status,
            user_agent=user_agent,
            cookies=cookies,
            headers=dict(solution.get("headers") or {}),
        )

    async def destroy_session(self, session: str) -> None:
        """Explicitly destroy a FlareSolverr session, releasing its memory."""
        await self._post({"cmd": "sessions.destroy", "session": session})


def require_httpx() -> None:
    """Raise DependencyMissingError if httpx isn't installed.

    Called by callers that want a clean error rather than an ImportError.
    """
    try:
        import httpx  # noqa: F401
    except ImportError as exc:
        raise DependencyMissingError(
            "FlareSolverr integration requires httpx.",
            "Install with: pip install agent-env-core[flare-solverr]",
        ) from exc
