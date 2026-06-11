"""Terminal command safety checks."""

import os

from agent_env_core.exceptions import DestructiveCommandError

from .format_filesystem_blocklist import FORMAT_FILESYSTEM_PATTERNS


def assert_safe_command(argv: list[str]) -> None:
    """Raise when argv matches the dedicated destructive-command policy module."""
    if os.environ.get("ALLOW_DESTRUCTIVE") == "1" or not argv:
        return
    lowered = [part.lower() for part in argv]
    executable = lowered[0].split("/")[-1]
    for pattern in FORMAT_FILESYSTEM_PATTERNS:
        first = pattern[0].lower()
        if executable == first or executable.startswith(first):
            if len(pattern) == 1 or all(token.lower() in lowered for token in pattern[1:]):
                raise DestructiveCommandError(
                    "Command refused by terminal safety policy.",
                    "Set ALLOW_DESTRUCTIVE=1 only after verifying the command is intentional.",
                )
