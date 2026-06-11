"""Desktop backend protocol."""

from typing import Protocol


class DesktopBackend(Protocol):
    """Protocol implemented by platform screen-capture backends."""

    name: str

    def capture_screen(self) -> bytes:
        """Return screenshot image bytes."""

    def screen_size(self) -> tuple[int, int]:
        """Return screen width and height in pixels."""
