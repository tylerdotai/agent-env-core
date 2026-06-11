"""Private stale-DOM retry helpers for semantic Playwright locators."""

from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def _retry_stale(action: Callable[[], Awaitable[T]], attempts: int = 3) -> T:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await action()
        except Exception as exc:  # pragma: no cover - Playwright exception types are optional
            last_error = exc
            if "stale" not in str(exc).lower() and "detached" not in str(exc).lower():
                raise
    assert last_error is not None
    raise last_error


async def _click_by_role(page: object, role: str, name: str) -> None:
    await _retry_stale(lambda: page.get_by_role(role, name=name).click())  # type: ignore[attr-defined]


async def _type_by_text(page: object, text: str, value: str) -> None:
    await _retry_stale(lambda: page.get_by_text(text).fill(value))  # type: ignore[attr-defined]
