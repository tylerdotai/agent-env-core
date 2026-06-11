"""Package exception hierarchy."""


class AgentEnvCoreError(Exception):
    """Base package error with an optional recovery suggestion."""

    def __init__(self, message: str, recovery_suggestion: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.recovery_suggestion = recovery_suggestion


class DependencyMissingError(AgentEnvCoreError):
    """A required optional dependency is not installed."""


class ActionFailedError(AgentEnvCoreError):
    """An environment action failed."""


class TimeoutExceededError(AgentEnvCoreError):
    """An operation exceeded its allowed runtime."""


class InteractivePromptException(AgentEnvCoreError):
    """A command emitted an interactive prompt."""


class DestructiveCommandError(AgentEnvCoreError):
    """A command was refused by terminal safety policy."""


class PlatformUnsupportedError(AgentEnvCoreError):
    """The current platform is unsupported."""


class WaylandUnsupportedError(PlatformUnsupportedError):
    """The current Linux session is Wayland-only or lacks X11."""


class TemplateImageError(AgentEnvCoreError):
    """A template image is missing or unreadable."""


class CommandParseError(AgentEnvCoreError):
    """A terminal command string could not be parsed into argv."""
