"""Linux X11 mss backend."""

from io import BytesIO

from agent_env_core.exceptions import ActionFailedError, DependencyMissingError


class LinuxDesktopBackend:
    """Linux/X11 backend using mss for capture."""

    name = "linux-x11-mss"

    def __init__(self) -> None:
        self._last_size: tuple[int, int] | None = None

    def capture_screen(self) -> bytes:
        try:
            import mss
            from PIL import Image
        except ImportError as exc:
            raise DependencyMissingError(
                "mss and Pillow are required for desktop capture.",
                "Install agent-env-core[desktop].",
            ) from exc
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                raw = sct.grab(monitor)
                image = Image.frombytes("RGB", raw.size, raw.rgb)
                self._last_size = image.size
                output = BytesIO()
                image.save(output, format="PNG")
                return output.getvalue()
        except Exception as exc:
            raise ActionFailedError(
                "mss capture failed.", "Use a supported X11 graphical session."
            ) from exc

    def screen_size(self) -> tuple[int, int]:
        if self._last_size is None:
            self.capture_screen()
        assert self._last_size is not None
        return self._last_size
