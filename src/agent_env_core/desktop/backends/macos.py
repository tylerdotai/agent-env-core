"""macOS screencapture backend."""

import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from agent_env_core.exceptions import ActionFailedError, DependencyMissingError


class MacOSDesktopBackend:
    """macOS backend using the screencapture command."""

    name = "macos-screencapture"

    def __init__(self) -> None:
        self._last_size: tuple[int, int] | None = None

    def capture_screen(self) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = Path(tmp.name)
        try:
            result = subprocess.run(
                ["screencapture", "-x", str(path)], check=False, capture_output=True
            )
            if result.returncode != 0:
                raise ActionFailedError(
                    "screencapture failed.",
                    "Grant screen-recording permission and retry in a graphical session.",
                )
            data = path.read_bytes()
            self._last_size = _image_size(data)
            return data
        finally:
            path.unlink(missing_ok=True)

    def screen_size(self) -> tuple[int, int]:
        if self._last_size is None:
            self.capture_screen()
        assert self._last_size is not None
        return self._last_size


def _image_size(data: bytes) -> tuple[int, int]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise DependencyMissingError(
            "Pillow is required for desktop capture.", "Install agent-env-core[desktop]."
        ) from exc
    with Image.open(BytesIO(data)) as image:
        return image.width, image.height
