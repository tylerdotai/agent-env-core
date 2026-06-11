<div align="center">

# agent_env_core

**Async browser, desktop, and terminal environment tools for AI agent harnesses.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-40%20passed%2C%202%20skipped-brightgreen.svg)](#tests)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](#development)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://docs.astral.sh/ruff/)

Three drop-in async tools that give any Python agent the same three primitives:
navigate a browser, see the desktop, and run a shell command — with a single
response schema across all three domains.

[Install](#install) · [Quick start](#quick-start) · [API reference](#api-reference) · [Safety](#safety) · [Architecture](#architecture) · [Contributing](#contributing)

</div>

---

## Why agent_env_core?

Most agent frameworks reinvent the same three plumbing problems:

- **Browser automation** that breaks on every minor CSS change because it uses brittle XPaths
- **Screen capture + template matching** that only works on one OS
- **Shell execution** that hangs forever on `password:` prompts or `rm -rf` disasters

`agent_env_core` ships one canonical implementation of each, behind a single
typed envelope, with cross-platform shims, semantic selectors, and a real
safety net. MIT-licensed, no runtime dep bloat unless you opt in.

---

## Install

```bash
# Pick the slice you need (or use [all])
pip install agent-env-core[browser]      # Playwright + Pillow
pip install agent-env-core[desktop]      # mss, opencv-python, PyAutoGUI
pip install agent-env-core[terminal]     # stdlib-only (no extra deps)
pip install agent-env-core[all]          # everything

# Dev install (editable + tests + type checking)
pip install -e ".[all,dev]"
playwright install chromium              # required once for browser tests
```

Python **3.11 or newer** is required.

---

## Quick start

```python
import asyncio
from agent_env_core import (
    browser_navigate_and_render,
    desktop_capture_and_locate,
    terminal_execute_command,
)

async def main():
    # 1. Browser: navigate, get text + base64 JPEG of viewport
    page = await browser_navigate_and_render("https://example.com")
    print(page["data"]["title"], "->", page["data"]["final_url"])
    if page["visual_state"]:
        with open("viewport.jpg", "wb") as f:
            import base64
            f.write(base64.b64decode(page["visual_state"]))

    # 2. Desktop: capture screen, optionally template-match an icon
    screen = await desktop_capture_and_locate()  # full screen, no template
    print(f"Display: {screen['data']['screen_width']}x{screen['data']['screen_height']}")

    # 3. Terminal: run a command with timeout + interactive-prompt guard
    result = await terminal_execute_command("ls -la", timeout_sec=10)
    print(result["data"]["stdout"])

asyncio.run(main())
```

Every tool returns the **same envelope** (see [API reference](#api-reference)).

---

## API reference

All three public tools share this response schema:

```json
{
  "success": true,
  "execution_time_ms": 245,
  "domain": "browser | desktop | terminal",
  "tool_name": "string",
  "data": { },
  "visual_state": "base64_jpeg_string_or_null",
  "error": {
    "type": "null | TimeoutError | ActionFailed | ...",
    "message": "null | string",
    "recovery_suggestion": "null | string"
  }
}
```

### `browser_navigate_and_render(url: str) -> dict`

Navigate to `url` with Playwright Chromium (headless by default; set
`DEBUG_HEADED=1` to see the browser), wait for `networkidle`, then return the
rendered text + a base64 JPEG of the viewport (downsampled to ≤1280px wide).

Internals use semantic selectors (`page.get_by_role`, `page.get_by_text`) and
wrap click/type in a 3-retry stale-DOM loop.

### `desktop_capture_and_locate(template_image_path: str | None = None) -> dict`

Capture the full desktop display and (optionally) template-match a provided
image against it. Returns screen dimensions and a list of bounding boxes:

```json
{
  "data": {
    "screen_width": 2560,
    "screen_height": 1440,
    "backend": "macos",
    "display_server": "x11 | aqua | wayland-unsupported",
    "matches": [[x, y, w, h, confidence], ...],
    "match_count": 0
  }
}
```

Platform dispatch: macOS → `screencapture`, Windows → `mss`, Linux/X11 → `mss` +
`python-xlib`. **Wayland raises a clear `WaylandUnsupportedError`** (no
implicit fallback).

### `terminal_execute_command(command: str, timeout_sec: int = 30) -> dict`

Run `command` via `asyncio.create_subprocess_exec` (no shell — argv parsed from
the input string), stream stdout/stderr concurrently, hard-kill at `timeout_sec`
(default 30s, max 300s), truncate output at 10,000 chars per stream.

**Safety nets (see [Safety](#safety) for the full list):**

- `password:`, `[y/n]`, `Are you sure?` patterns raise `InteractivePromptException`
- Filesystem-formatting operations are refused unless `ALLOW_DESTRUCTIVE=1`
- `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, `PYTHONPATH` are stripped from the
  subprocess env (override with `ALLOW_ENV_OVERRIDE=1`)

---

## Safety

`agent_env_core` is designed to be safe by default in agent pipelines:

| Vector | Mitigation |
|---|---|
| **Interactive prompts** (`password:`, `[y/n]`) | Regex match on stdout → `InteractivePromptException` with `recovery_suggestion` |
| **Destructive commands** (filesystem-formatting patterns) | `DestructiveCommandError` raised unless `ALLOW_DESTRUCTIVE=1` is set in the agent's env |
| **Env hijack** (LD_PRELOAD, PYTHONPATH override) | Stripped from subprocess env unless `ALLOW_ENV_OVERRIDE=1` |
| **Hanging subprocesses** | Hard kill at `timeout_sec`; >300s is rejected with a structured error, not silently clamped |
| **Stale DOM** (browser re-render) | 3-retry loop on `TimeoutError` / `StaleElementReferenceError` |
| **Wayland screen capture** | Explicit `WaylandUnsupportedError` with a clear `recovery_suggestion` |
| **Excessive output** | 10,000 char truncation per stream to prevent context overflow |

The exact blocklist of destructive patterns lives in a single dedicated module
so it can be audited and tested in isolation.

---

## Architecture

```
agent_env_core/
├── browser/      # Playwright (semantic selectors, stale-DOM retry, JPEG screenshots)
├── desktop/      # Cross-platform screen capture + OpenCV template matching
│   └── backends/ # macos.py, windows.py, linux.py
└── terminal/     # argv exec, async streams, prompt detection, blocklist
```

- **One envelope, three domains** — every tool returns the same shape so the
  agent's reasoning loop can parse responses deterministically
- **Platform shims behind a Protocol** — `DesktopBackend` defines the contract;
  per-OS backends implement it; the factory dispatches by `sys.platform`
- **Typed exceptions, structured errors** — internal failures are caught and
  converted to the envelope, never leaked as raw tracebacks
- **py.typed marker** — full type hints, PEP 561 compliant

See [PLAN.md](PLAN.md) for the full design rationale.

---

## Tests

```bash
.venv/bin/pytest                  # 40 passed, 2 skipped in ~1.5s
.venv/bin/pytest --cov=agent_env_core
```

| Marker | Domain | Skip conditions |
|---|---|---|
| `@pytest.mark.browser` | Playwright | skips if `playwright` not installed |
| `@pytest.mark.desktop` | screen capture | skips if backend not importable on host |
| `@pytest.mark.terminal` | subprocess | always runnable |
| smoke tests | cross-domain | always runnable, low-cost sanity checks |

The 2 skipped tests on a typical macOS dev box are the Playwright browser tests
(browsers not yet installed locally). Run `playwright install chromium` to
enable them.

---

## Development

```bash
git clone <repo> && cd agent-toolkit
uv venv --python 3.11 .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
playwright install chromium

pytest                    # run the test suite
ruff check src tests      # lint
mypy src/agent_env_core   # type check
```

The `agent_env_core` source is under `src/`, tests under `tests/`, both
configured for hatchling in `pyproject.toml`. Optional extras let you install
only the slice you need.

---

## Contributing

Issues and PRs welcome. The toolkit follows these rules (any PR that violates
them will be asked to revise):

- **Tests first** — add or update tests in the same PR as behavior changes
- **One envelope** — all new tools return the same `Response` shape
- **No silent fallbacks** — failures surface as typed exceptions, not as
  `success: True` with empty data
- **No enums of destructive patterns in prose** — keep the blocklist in
  `terminal/format_filesystem_blocklist.py` so it has a single audit point
- **Cross-platform by default** — if you add a desktop feature, ship shims for
  macOS, Windows, *and* Linux (or raise a `PlatformUnsupportedError` with a
  clear `recovery_suggestion`)

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for the full text.

---

## Acknowledgments

- [Playwright](https://playwright.dev/python/) — browser automation
- [OpenCV](https://opencv.org/) — template matching
- [mss](https://python-mss.readthedocs.io/) — cross-platform screen capture
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template) —
  README structure
- [Anthropic's skill design guide](https://github.com/anthropics/skills) —
  inspiration for the agent-side ergonomics

---

<div align="center">
Built for agents that need to actually do things in the real world.
</div>
