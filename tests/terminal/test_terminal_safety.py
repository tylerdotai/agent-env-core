import pytest

from agent_env_core.terminal import safety


@pytest.mark.terminal
def test_safety_module_refuses_monkeypatched_policy(monkeypatch):
    monkeypatch.setattr(safety, "FORMAT_FILESYSTEM_PATTERNS", (("blocked-tool",),))
    with pytest.raises(Exception) as excinfo:
        safety.assert_safe_command(["blocked-tool", "target"])
    assert excinfo.value.recovery_suggestion


@pytest.mark.terminal
def test_safety_override_allows_monkeypatched_policy(monkeypatch):
    monkeypatch.setattr(safety, "FORMAT_FILESYSTEM_PATTERNS", (("blocked-tool",),))
    monkeypatch.setenv("ALLOW_DESTRUCTIVE", "1")
    safety.assert_safe_command(["blocked-tool", "target"])
