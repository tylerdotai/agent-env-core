"""Subprocess environment sanitization."""

import os

_BLOCKED_ENV = ("LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "PYTHONPATH")


def build_subprocess_env() -> dict[str, str]:
    """Return a subprocess environment with injection-related variables stripped by default."""
    env = dict(os.environ)
    if env.get("ALLOW_ENV_OVERRIDE") != "1":
        for key in _BLOCKED_ENV:
            env.pop(key, None)
    return env
