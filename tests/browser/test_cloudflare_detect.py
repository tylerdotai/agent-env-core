"""Tests for the Cloudflare/DDoS-GUARD challenge detector."""

from __future__ import annotations

import pytest

from agent_env_core.browser.cloudflare_detect import (
    detect_from_headers,
    detect_from_text,
    detect_from_url,
)


def test_detect_from_headers_positive():
    r = detect_from_headers({"server": "cloudflare", "cf-ray": "abc123"})
    assert r.detected is True
    assert "cloudflare" in (r.reason or "").lower()
    assert "server: cloudflare" in r.markers


def test_detect_from_headers_case_insensitive():
    r = detect_from_headers({"Server": "Cloudflare", "CF-RAY": "abc"})
    assert r.detected is True


def test_detect_from_headers_negative():
    r = detect_from_headers({"server": "nginx", "content-type": "text/html"})
    assert r.detected is False


def test_detect_from_headers_empty():
    assert detect_from_headers(None).detected is False
    assert detect_from_headers({}).detected is False


def test_detect_from_url_challenge_platform():
    r = detect_from_url("https://example.com/cdn-cgi/challenge-platform/h/b")
    assert r.detected is True
    assert "/cdn-cgi/challenge-platform" in (r.reason or "")


def test_detect_from_url_normal():
    r = detect_from_url("https://example.com/articles/2024")
    assert r.detected is False


def test_detect_from_text_cloudflare_challenge():
    r = detect_from_text(
        "Checking your browser before accessing example.com.\nPlease wait..."
    )
    assert r.detected is True
    assert "checking your browser" in (r.reason or "").lower()


def test_detect_from_text_ddos_guard():
    r = detect_from_text("DDoS-GUARD protection. Please wait...")
    assert r.detected is True


def test_detect_from_text_normal_page():
    r = detect_from_text("Welcome to the homepage. Today's news is...")
    assert r.detected is False


def test_detect_from_text_empty():
    assert detect_from_text("").detected is False


def test_detect_from_text_case_insensitive():
    r = detect_from_text("PLEASE WAIT WHILE WE ARE CHECKING YOUR BROWSER")
    assert r.detected is True
