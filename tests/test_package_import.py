import inspect

import agent_env_core


def test_package_exports_exact_public_tools():
    assert agent_env_core.__all__ == [
        "browser_navigate_and_render",
        "desktop_capture_and_locate",
        "terminal_execute_command",
    ]
    for name in agent_env_core.__all__:
        fn = getattr(agent_env_core, name)
        assert inspect.iscoroutinefunction(fn)
        assert fn.__doc__
