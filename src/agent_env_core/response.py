"""Shared response envelope helpers."""

from typing import Any

from .exceptions import ActionFailedError, AgentEnvCoreError, TimeoutExceededError

Response = dict[str, Any]


def error_type(exc: BaseException) -> str:
    """Return the public error type for an exception."""
    if isinstance(exc, TimeoutExceededError):
        return "TimeoutError"
    if isinstance(exc, ActionFailedError):
        return "ActionFailed"
    name = exc.__class__.__name__
    if name.endswith("Exception"):
        return name
    if name.endswith("Error"):
        return name
    return f"{name}Error"


def make_response(
    *,
    success: bool,
    execution_time_ms: int,
    domain: str,
    tool_name: str,
    data: dict[str, Any] | None = None,
    visual_state: str | None = None,
    error: BaseException | None = None,
) -> Response:
    """Build the exact public response envelope for all tools."""
    error_obj: dict[str, str | None]
    if success:
        error_obj = {"type": None, "message": None, "recovery_suggestion": None}
    else:
        message = str(error) if error is not None else "Action failed"
        recovery = error.recovery_suggestion if isinstance(error, AgentEnvCoreError) else None
        error_obj = {
            "type": error_type(error) if error is not None else "ActionFailed",
            "message": message,
            "recovery_suggestion": recovery,
        }
    return {
        "success": success,
        "execution_time_ms": execution_time_ms,
        "domain": domain,
        "tool_name": tool_name,
        "data": data or {},
        "visual_state": visual_state,
        "error": error_obj,
    }
