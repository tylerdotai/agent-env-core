import pytest

from agent_env_core.desktop import factory
from agent_env_core.exceptions import PlatformUnsupportedError, WaylandUnsupportedError


def test_factory_unknown_platform(monkeypatch):
    monkeypatch.setattr(factory.sys, "platform", "mystery")
    with pytest.raises(PlatformUnsupportedError):
        factory.get_desktop_backend()


def test_factory_macos_dispatch(monkeypatch):
    monkeypatch.setattr(factory.sys, "platform", "darwin")
    backend = factory.get_desktop_backend()
    assert backend.__class__.__name__ == "MacOSDesktopBackend"


def test_factory_windows_dispatch(monkeypatch):
    monkeypatch.setattr(factory.sys, "platform", "win32")
    backend = factory.get_desktop_backend()
    assert backend.__class__.__name__ == "WindowsDesktopBackend"


def test_linux_wayland_detection(monkeypatch):
    monkeypatch.setattr(factory.sys, "platform", "linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    with pytest.raises(WaylandUnsupportedError):
        factory.get_desktop_backend()
