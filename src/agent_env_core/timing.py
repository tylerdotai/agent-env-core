"""Timing helpers."""

from time import monotonic


class Timer:
    """Monotonic millisecond timer."""

    def __init__(self) -> None:
        self._started = monotonic()

    def elapsed_ms(self) -> int:
        """Return elapsed milliseconds since construction."""
        return max(0, round((monotonic() - self._started) * 1000))
