"""Detect Cloudflare and DDoS-GUARD challenges in a Playwright page.

The detection looks at three layers, in order of cost:

1. Response headers (``Server: cloudflare``, ``cf-ray``)
2. HTML markers in the rendered DOM (challenge iframe, "Checking your
   browser before accessing", turnstile div, etc.)
3. URL pattern (``/cdn-cgi/challenge-platform/``)

Layer 1+2 are usually sufficient; layer 3 is a fallback for sites that
manage to load a page with CF cookies already set (rare).

Note: this module imports playwright lazily. The base package import
must not require playwright to be installed; only the
``[browser]`` extra does.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


# Markers that, if present, strongly indicate a Cloudflare/DDoS-GUARD wall.
# Matched case-insensitively against the rendered text content.
_TEXT_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"checking your browser before accessing", re.IGNORECASE),
    re.compile(r"please wait while we are checking your browser", re.IGNORECASE),
    re.compile(r"ddos-guard", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"attention required! \| cloudflare", re.IGNORECASE),
    re.compile(r"cloudflare to protect this site from abuse", re.IGNORECASE),
)

# URL substrings that imply a challenge page (not a solved app).
_URL_MARKERS: tuple[str, ...] = (
    "/cdn-cgi/challenge-platform/",
    "/cdn-cgi/challenge",
    "/__cf_chl_jschl_chk_elem",
    "/ddos-guard-check",
)

# Response headers that confirm Cloudflare is in the path.
_HEADER_MARKERS: tuple[str, ...] = (
    "server: cloudflare",
    "cf-ray",
    "cf-mitigated",
)


@dataclass(frozen=True)
class CloudflareDetection:
    """Result of scanning a page for Cloudflare/DDoS-GUARD challenges."""

    detected: bool
    reason: str | None = None  # human-readable: which marker fired
    markers: tuple[str, ...] = ()  # all markers that fired, for logging


def detect_from_headers(headers: dict[str, str] | None) -> CloudflareDetection:
    """Detect Cloudflare from the response headers of the initial navigation.

    Works on the headers that Playwright's ``response.headers`` exposes.
    """
    if not headers:
        return CloudflareDetection(detected=False)
    fired: list[str] = []
    for header_name, header_value in headers.items():
        full = f"{header_name.lower()}: {header_value.lower()}"
        for marker in _HEADER_MARKERS:
            if marker in full:
                fired.append(marker)
    if fired:
        return CloudflareDetection(
            detected=True,
            reason=f"response headers contain: {', '.join(fired[:3])}",
            markers=tuple(fired),
        )
    return CloudflareDetection(detected=False)


def detect_from_url(url: str) -> CloudflareDetection:
    """Detect Cloudflare challenge redirects from the URL alone."""
    lower = url.lower()
    fired = [m for m in _URL_MARKERS if m in lower]
    if fired:
        return CloudflareDetection(
            detected=True,
            reason=f"URL contains challenge path: {fired[0]}",
            markers=tuple(fired),
        )
    return CloudflareDetection(detected=False)


def detect_from_text(text: str) -> CloudflareDetection:
    """Detect Cloudflare/DDoS-GUARD from the page's rendered text content.

    Use the result of ``page.inner_text("body")`` or
    ``page.evaluate("document.body.innerText")``.
    """
    if not text:
        return CloudflareDetection(detected=False)
    fired: list[str] = []
    for pattern in _TEXT_MARKERS:
        if pattern.search(text):
            fired.append(pattern.pattern)
    if fired:
        return CloudflareDetection(
            detected=True,
            reason=f"page text contains: {fired[0]}",
            markers=tuple(fired),
        )
    return CloudflareDetection(detected=False)


async def detect_from_page(page: Any) -> CloudflareDetection:
    """Detect Cloudflare from a live Playwright Page.

    Combines header, URL, and text detection. Imported lazily because
    this module is referenced from non-browser code paths.
    """
    try:
        url = page.url
    except Exception:  # noqa: BLE001 — Playwright can throw on closed pages
        url = ""
    url_result = detect_from_url(url) if url else CloudflareDetection(detected=False)

    text_result = CloudflareDetection(detected=False)
    try:
        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:  # noqa: BLE001
        text = ""
    text_result = detect_from_text(text or "")

    if url_result.detected or text_result.detected:
        primary = url_result if url_result.detected else text_result
        return CloudflareDetection(
            detected=True,
            reason=primary.reason,
            markers=url_result.markers + text_result.markers,
        )
    return CloudflareDetection(detected=False)
