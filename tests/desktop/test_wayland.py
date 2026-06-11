import pytest

from agent_env_core.desktop import factory
from agent_env_core.desktop.capture import desktop_capture_and_locate


@pytest.mark.desktop
@pytest.mark.asyncio
async def test_wayland_returns_structured_error(monkeypatch):
    monkeypatch.setattr(factory.sys, "platform", "linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    response = await desktop_capture_and_locate()
    assert not response["success"]
    assert response["error"]["type"] == "WaylandUnsupportedError"
    assert response["error"]["recovery_suggestion"]
