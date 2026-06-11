from agent_env_core.terminal.env import build_subprocess_env


def test_env_sanitization_strips_by_default(monkeypatch):
    monkeypatch.setenv("LD_PRELOAD", "x")
    monkeypatch.setenv("DYLD_INSERT_LIBRARIES", "x")
    monkeypatch.setenv("PYTHONPATH", "x")
    monkeypatch.delenv("ALLOW_ENV_OVERRIDE", raising=False)
    env = build_subprocess_env()
    assert "LD_PRELOAD" not in env
    assert "DYLD_INSERT_LIBRARIES" not in env
    assert "PYTHONPATH" not in env


def test_env_sanitization_allows_override(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "x")
    monkeypatch.setenv("ALLOW_ENV_OVERRIDE", "1")
    assert build_subprocess_env()["PYTHONPATH"] == "x"
