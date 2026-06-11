from agent_env_core.exceptions import ActionFailedError
from agent_env_core.response import make_response


def test_success_response_schema(response_schema):
    response = make_response(
        success=True,
        execution_time_ms=1,
        domain="terminal",
        tool_name="tool",
        data={"ok": True},
    )
    response_schema(response)
    assert response["error"] == {"type": None, "message": None, "recovery_suggestion": None}


def test_error_response_schema(response_schema):
    response = make_response(
        success=False,
        execution_time_ms=1,
        domain="terminal",
        tool_name="tool",
        error=ActionFailedError("failed", "retry"),
    )
    response_schema(response)
    assert response["error"]["type"] == "ActionFailed"
    assert response["error"]["recovery_suggestion"] == "retry"
