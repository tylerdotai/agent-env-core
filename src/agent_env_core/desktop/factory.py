"""Desktop backend factory."""

import os
import sys

from agent_env_core.exceptions import PlatformUnsupportedError, WaylandUnsupportedError

from .backend import DesktopBackend


def _linux_display_server() -> str:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    display = os.environ.get("DISPLAY")
    if session_type == "wayland" or (wayland_display and not display):
        raise WaylandUnsupportedError(
            "Wayland-only desktop capture is not supported.",
            "Use an X11 or XWayland-supported graphical session.",
        )
    if not display:
        raise WaylandUnsupportedError(
            "No supported X11 display is available.",
            "Run inside a graphical X11 session with DISPLAY set.",
        )
    return "x11"


def display_server() -> str:
    """Return the current display-server label."""
    if sys.platform == "darwin":
        return "quartz"
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return _linux_display_server()
    return "unknown"


def get_desktop_backend() -> DesktopBackend:
    """Construct the backend matching the current platform."""
    if sys.platform == "darwin":
        from .backends.macos import MacOSDesktopBackend

        return MacOSDesktopBackend()
    if sys.platform == "win32":
        from .backends.windows import WindowsDesktopBackend

        return WindowsDesktopBackend()
    if sys.platform.startswith("linux"):
        _linux_display_server()
        from .backends.linux import LinuxDesktopBackend

        return LinuxDesktopBackend()
    raise PlatformUnsupportedError(
        "Platform is not supported.", "Use macOS, Windows, or Linux/X11."
    )
