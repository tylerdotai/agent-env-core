import pytest

from agent_env_core import exceptions
from agent_env_core.response import error_type


@pytest.mark.parametrize(
    "cls",
    [
        exceptions.AgentEnvCoreError,
        exceptions.DependencyMissingError,
        exceptions.ActionFailedError,
        exceptions.TimeoutExceededError,
        exceptions.InteractivePromptException,
        exceptions.DestructiveCommandError,
        exceptions.PlatformUnsupportedError,
        exceptions.WaylandUnsupportedError,
        exceptions.TemplateImageError,
        exceptions.CommandParseError,
    ],
)
def test_exceptions_have_message_and_recovery(cls):
    exc = cls("message", "recover")
    assert str(exc) == "message"
    assert exc.recovery_suggestion == "recover"


def test_timeout_maps_to_timeout_error():
    assert error_type(exceptions.TimeoutExceededError("late")) == "TimeoutError"
