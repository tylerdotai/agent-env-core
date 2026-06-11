# agent_env_core Build Plan

Source spec: `/tmp/agent-toolkit-spec.md`  
Output constraint: this plan is saved at `.omo/plans/PLAN.md` because Prometheus may only write plan artifacts under `.omo/`.

## 0. Executive Summary

Build a greenfield Python 3.11+ package named `agent_env_core` that exposes three fully async public tools:

1. `browser_navigate_and_render(url: str) -> dict`
2. `desktop_capture_and_locate(template_image_path: str = None) -> dict`
3. `terminal_execute_command(command: str, timeout_sec: int = 30) -> dict`

All public tools return the same response envelope:

```json
{
  "success": true,
  "execution_time_ms": 245,
  "domain": "browser | desktop | terminal",
  "tool_name": "string",
  "data": {},
  "visual_state": "base64_jpeg_string_or_null",
  "error": {
    "type": "null | TimeoutError | ActionFailed | ...",
    "message": "null | string",
    "recovery_suggestion": "null | string"
  }
}
```

Key decisions for the executor:

- Use `src/` layout.
- Every public async function must have complete type hints and a docstring describing inputs, returned schema, failure behavior, and optional dependency requirements.
- Use stdlib `logging`, not Loguru, to minimize runtime dependencies. Loguru remains a future non-blocking option.
- Public tool functions catch internal typed exceptions and convert them into the shared response schema.
- Internal helpers raise exceptions defined only in `agent_env_core/exceptions.py`.
- Terminal execution must not use shell execution; parse `command: str` into an argv list and call `asyncio.create_subprocess_exec(*argv, ...)`.
- Timeout values greater than 300 seconds are rejected with a structured `TimeoutError` response instead of being clamped silently.
- Non-zero terminal exit codes return `success: false` with `error.type = "CommandFailed"` and include stdout/stderr in `data`.
- The destructive-pattern blocklist is a separate safety module, referenced as `agent_env_core/terminal/format_filesystem_blocklist.py` through `agent_env_core/terminal/safety.py`. Do not enumerate destructive patterns in source comments, tests, README text, or this plan.

## 1. Package Layout

Create exactly this tree during implementation:

```text
agent-toolkit/
├── LICENSE
├── README.md
├── pyproject.toml
├── src/
│   └── agent_env_core/
│       ├── __init__.py
│       ├── exceptions.py
│       ├── py.typed
│       ├── response.py
│       ├── timing.py
│       ├── browser/
│       │   ├── __init__.py
│       │   ├── render.py
│       │   ├── screenshot.py
│       │   └── stale_retry.py
│       ├── desktop/
│       │   ├── __init__.py
│       │   ├── backend.py
│       │   ├── capture.py
│       │   ├── factory.py
│       │   ├── locate.py
│       │   └── backends/
│       │       ├── __init__.py
│       │       ├── linux.py
│       │       ├── macos.py
│       │       └── windows.py
│       └── terminal/
│           ├── __init__.py
│           ├── command.py
│           ├── env.py
│           ├── format_filesystem_blocklist.py
│           ├── prompts.py
│           ├── safety.py
│           └── stream.py
└── tests/
    ├── conftest.py
    ├── test_exceptions.py
    ├── test_package_import.py
    ├── test_response_schema.py
    ├── browser/
    │   ├── test_browser_render.py
    │   └── test_browser_screenshot.py
    ├── desktop/
    │   ├── test_backend_factory.py
    │   ├── test_desktop_capture.py
    │   ├── test_template_matching.py
    │   └── test_wayland.py
    ├── smoke/
    │   └── test_smoke_tools.py
    └── terminal/
        ├── test_command_parse.py
        ├── test_env_sanitization.py
        ├── test_prompt_detection.py
        ├── test_streaming_timeout.py
        └── test_terminal_safety.py
```

Do not create additional public modules unless a test requires factoring a private helper. If a helper is needed, keep it private inside the planned file rather than expanding the tree.

## 2. pyproject.toml

Use this dependency manifest exactly, except the executor may update pins only if installation fails and must record the reason in the implementation notes.

```toml
[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "agent-env-core"
version = "0.1.0"
description = "Async browser, desktop, and terminal environment tools for agents."
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }
authors = [{ name = "agent_env_core maintainers" }]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Typing :: Typed"
]
dependencies = []

[project.optional-dependencies]
browser = [
  "playwright==1.49.1",
  "Pillow==11.1.0"
]
desktop = [
  "mss==10.0.0",
  "opencv-python==4.10.0.84",
  "numpy==2.2.1",
  "Pillow==11.1.0",
  "PyAutoGUI==0.9.54",
  "pytesseract==0.3.13",
  "python-xlib==0.33; platform_system == 'Linux'"
]
terminal = []
all = [
  "agent-env-core[browser,desktop,terminal]"
]
dev = [
  "pytest==8.3.4",
  "pytest-asyncio==0.25.2",
  "pytest-cov==6.0.0",
  "ruff==0.9.2",
  "mypy==1.14.1"
]

[tool.hatch.build.targets.wheel]
packages = ["src/agent_env_core"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
  "browser: tests requiring Playwright and installed browser binaries",
  "desktop: tests requiring a graphical desktop/display server",
  "terminal: tests for terminal command execution",
  "smoke: package-level smoke tests"
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC", "ANN"]
ignore = ["ANN401"]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["agent_env_core"]
```

Dependency notes:

- Stdlib `logging` is used; no Loguru dependency.
- `pytesseract` is included because the spec names it for Windows platform capability, but OCR is explicitly out of scope for `desktop_capture_and_locate` unless a future spec adds OCR output.
- `terminal` has no runtime dependencies.
- The `all` extra aggregates all three runtime domains.

## 3. File-by-File Responsibilities

### Root files

`LICENSE`: MIT license text for `agent_env_core` itself.

`README.md`: Minimal package overview, installation examples for each extra, public API names, platform support matrix, and safety warning that destructive terminal patterns are refused via the separate safety module. Do not list destructive patterns.

`pyproject.toml`: Build backend, project metadata, optional extras, dev dependencies, pytest markers, Ruff settings, and strict mypy settings exactly as specified above.

### `src/agent_env_core/`

`__init__.py`: Export only the three public async tools and package version metadata if needed. Keep imports lazy enough that installing only one optional extra does not import unavailable domain dependencies at package import time.

`exceptions.py`: Define all package exception classes: `AgentEnvCoreError`, `DependencyMissingError`, `ActionFailedError`, `TimeoutExceededError`, `InteractivePromptException`, `DestructiveCommandError`, `PlatformUnsupportedError`, `WaylandUnsupportedError`, `TemplateImageError`, and `CommandParseError`. Every exception must carry a human-readable message and optional `recovery_suggestion`.

`py.typed`: Marker file declaring the package provides inline type information.

`response.py`: Define the shared response-construction helper used by all three tools. It must always produce the exact top-level keys from the spec, with `error.type`, `error.message`, and `error.recovery_suggestion` set to null-equivalent values on success. It also maps internal exceptions into structured error objects.

`timing.py`: Provide a monotonic timer helper for measuring `execution_time_ms`. All public tools use this helper so timings are consistent.

### `src/agent_env_core/browser/`

`browser/__init__.py`: Re-export `browser_navigate_and_render` without importing desktop or terminal dependencies.

`browser/render.py`: Implement `browser_navigate_and_render(url: str) -> dict` with full type hints and a public docstring. It validates URL input, launches Playwright Chromium headless by default, uses headed mode only when `DEBUG_HEADED=1`, navigates with `wait_until="networkidle"`, captures page text content, captures a viewport screenshot, and returns the shared response schema. `data` keys must be: `requested_url`, `final_url`, `title`, `text_content`, `viewport_width`, `viewport_height`, `screenshot_width`, `screenshot_height`, `screenshot_format`, and `wait_until`.

`browser/screenshot.py`: Convert the Playwright screenshot bytes to JPEG, downsample to a maximum width of 1280 pixels while preserving aspect ratio, encode base64, and report final dimensions. JPEG quality must be 70.

`browser/stale_retry.py`: Provide private helpers for retrying stale-DOM click/type actions up to 3 attempts using semantic Playwright locator patterns. This is included only to satisfy the spec's stale-DOM retry requirement; it must not create public click/type APIs or expand `browser_navigate_and_render` inputs.

### `src/agent_env_core/desktop/`

`desktop/__init__.py`: Re-export `desktop_capture_and_locate` without importing browser or terminal dependencies.

`desktop/backend.py`: Define the `DesktopBackend` `Protocol` with `name: str`, `capture_screen() -> bytes`, and `screen_size() -> tuple[int, int]`. All OS-specific logic is hidden behind this protocol.

`desktop/capture.py`: Implement `desktop_capture_and_locate(template_image_path: str | None = None) -> dict` with full type hints and a public docstring. It selects a backend through `factory.py`, captures the screen, optionally performs template matching through `locate.py`, and returns the shared schema. `data` keys must be: `screen_width`, `screen_height`, `backend`, `display_server`, `template_image_path`, `matches`, `match_count`, and `coordinate_system`. `visual_state` contains a base64 JPEG of the captured screen.

`desktop/factory.py`: Dispatch by `sys.platform`: `darwin` to `MacOSDesktopBackend`, `win32` to `WindowsDesktopBackend`, and Linux platforms to `LinuxDesktopBackend`. Unknown platforms raise `PlatformUnsupportedError`. Linux Wayland detection happens before backend construction.

`desktop/locate.py`: Implement OpenCV template matching when `template_image_path` is provided. Validate that the template exists and is readable. Return `matches` as JSON-compatible 5-item arrays in the exact order `[x, y, w, h, confidence]`. Use a default confidence threshold of `0.8` and non-maximum suppression to avoid duplicate overlapping matches.

`desktop/backends/__init__.py`: Internal backend package marker only.

`desktop/backends/macos.py`: macOS backend using the `screencapture` command-line tool as the primary capture path. It reports display dimensions from the captured image. Quartz/Vision are not required for this first implementation; Vision/OCR remains deferred.

`desktop/backends/windows.py`: Windows backend using `mss` for capture and `pyautogui` only for screen dimension fallback. It must not implement mouse/keyboard automation. `pytesseract` is not invoked in this plan.

`desktop/backends/linux.py`: Linux/X11 backend using `mss` for capture. Detect Wayland through `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, and missing/invalid `DISPLAY`; raise `WaylandUnsupportedError` with a clear recovery suggestion when Wayland is active or X11 is unavailable.

### `src/agent_env_core/terminal/`

`terminal/__init__.py`: Re-export `terminal_execute_command` without importing browser or desktop dependencies.

`terminal/command.py`: Implement `terminal_execute_command(command: str, timeout_sec: int = 30) -> dict` with full type hints and a public docstring. Validate timeout range, parse command into argv, sanitize environment, perform safety checks, launch `asyncio.create_subprocess_exec`, stream stdout/stderr concurrently, enforce timeout, truncate each stream at 10,000 characters, and return the shared schema. `data` keys must be: `command`, `argv`, `exit_code`, `stdout`, `stderr`, `stdout_truncated`, `stderr_truncated`, `timed_out`, and `duration_ms`.

`terminal/env.py`: Build the subprocess environment. Remove `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, and `PYTHONPATH` unless `ALLOW_ENV_OVERRIDE=1` is set.

`terminal/format_filesystem_blocklist.py`: Separate safety module containing the destructive filesystem-formatting blocklist referenced by `safety.py`. Do not document the concrete patterns outside this module.

`terminal/prompts.py`: Define the interactive prompt detection regex for password, confirmation, yes/no, and are-you-sure style prompts. When matched in stdout or stderr streaming, raise `InteractivePromptException` internally and return a structured error publicly.

`terminal/safety.py`: Check the parsed argv/command against `format_filesystem_blocklist.py`. Refuse matching commands unless `ALLOW_DESTRUCTIVE=1` is set, raising `DestructiveCommandError` with a `recovery_suggestion`. This module is the only public reference point for destructive-command policy.

`terminal/stream.py`: Concurrently read stdout and stderr line by line, preserve ordering within each stream, detect interactive prompts while streaming, and truncate each stream at 10,000 characters with boolean truncation flags.

### Tests

`tests/conftest.py`: Shared pytest fixtures for response schema validation, dependency availability checks, display availability checks, temporary template images, and safe command helpers. It must not enumerate destructive command patterns.

`tests/test_exceptions.py`: Assert every custom exception can be instantiated with message and recovery suggestion and maps to the expected structured error type.

`tests/test_package_import.py`: Assert `import agent_env_core` succeeds without optional browser/desktop dependencies installed and exposes exactly the three public tool functions.

`tests/test_response_schema.py`: Assert success and error responses contain exactly the required top-level keys and nested error keys.

`tests/browser/test_browser_render.py`: Browser tests for valid navigation, invalid URL, navigation timeout, `DEBUG_HEADED` handling by configuration inspection, and missing Playwright browser skip behavior.

`tests/browser/test_browser_screenshot.py`: Assert screenshot JPEG output is base64, maximum width is 1280, quality conversion path succeeds, and `visual_state` is populated on successful browser render.

`tests/desktop/test_backend_factory.py`: Assert platform dispatch selects the expected backend class for mocked `sys.platform` values and raises `PlatformUnsupportedError` for unknown platforms.

`tests/desktop/test_desktop_capture.py`: Assert capture returns screen dimensions, backend name, display server, and JPEG `visual_state`; skip when no display is available.

`tests/desktop/test_template_matching.py`: Assert template matching returns JSON-compatible `[x, y, w, h, confidence]` arrays, handles missing template files with `TemplateImageError`, and reports `match_count` accurately.

`tests/desktop/test_wayland.py`: Assert mocked Wayland environment returns a structured `WaylandUnsupportedError` response with a clear recovery suggestion.

`tests/smoke/test_smoke_tools.py`: Import package and call each public tool with safe inputs. Browser smoke skips if Playwright browsers are unavailable. Desktop smoke skips if display is unavailable. Terminal smoke runs a safe Python interpreter command.

`tests/terminal/test_command_parse.py`: Assert shell features are not executed implicitly, empty commands return `CommandParseError`, and parsed argv is recorded in response data for safe commands.

`tests/terminal/test_env_sanitization.py`: Assert blocked environment variables are absent by default and preserved only when `ALLOW_ENV_OVERRIDE=1` is set.

`tests/terminal/test_prompt_detection.py`: Assert interactive prompt detection triggers `InteractivePromptException` internally and a structured public error response.

`tests/terminal/test_streaming_timeout.py`: Assert stdout/stderr are streamed concurrently, timeout kills the process at `timeout_sec`, `timeout_sec > 300` is rejected, and per-stream output truncation flags are set at 10,000 characters.

`tests/terminal/test_terminal_safety.py`: Assert safety checks call the separate safety module and produce `DestructiveCommandError` with recovery suggestion when the module reports a blocked command. Tests must use monkeypatching or module-level fixtures and must not include concrete destructive command examples in the test source.

## 4. Platform Shim Strategy

Desktop support is isolated behind `DesktopBackend`.

### Dispatch rules

1. `sys.platform == "darwin"` → `MacOSDesktopBackend`
2. `sys.platform == "win32"` → `WindowsDesktopBackend`
3. `sys.platform.startswith("linux")` → check Wayland/X11, then `LinuxDesktopBackend`
4. Anything else → `PlatformUnsupportedError`

### macOS

- Primary capture path: `screencapture` command-line tool invoked without UI prompts.
- Read captured image bytes, derive dimensions via Pillow, and return JPEG base64.
- Do not require PyObjC, Quartz bindings, or Vision for the first implementation.
- If `screencapture` fails, return `ActionFailed` with a recovery suggestion about screen-recording permissions.

### Windows

- Primary capture path: `mss`.
- Dimension fallback: `pyautogui.size()` if `mss` metadata is unavailable.
- Do not implement clicking, typing, OCR, or keyboard automation.
- If capture fails due permissions/session isolation, return `ActionFailed` with recovery suggestion.

### Linux/X11

- Detect Wayland before capture:
  - Treat `XDG_SESSION_TYPE=wayland` as Wayland.
  - Treat presence of `WAYLAND_DISPLAY` with missing `DISPLAY` as Wayland-only.
  - Treat missing `DISPLAY` as no supported graphical display.
- Wayland returns `WaylandUnsupportedError` with recovery suggestion to use X11/XWayland-supported capture in a graphical session.
- X11 capture uses `mss` and may rely on `python-xlib` availability.

### Template matching

- Capture full screen first.
- If `template_image_path is None`, skip matching and return `matches: []`, `match_count: 0`.
- If provided, validate path exists and can be decoded as an image.
- Use OpenCV normalized correlation with default threshold `0.8`.
- Return matches as `[x, y, w, h, confidence]` arrays in screen-pixel coordinates.
- Document percentage-based coordinates as the preferred downstream convention, but do not implement public click APIs in this package.

## 5. Test Plan

### Install commands for executor

```bash
python -m pip install -e '.[all,dev]'
python -m playwright install chromium
```

If a CI job intentionally excludes optional extras, run only the matching subset below.

### Full local verification

```bash
python -m pytest
python -m ruff check .
python -m mypy src/agent_env_core
```

### Schema and import tests

Command:

```bash
python -m pytest tests/test_response_schema.py tests/test_exceptions.py tests/test_package_import.py -q
```

Assertions:

- Response object has exactly `success`, `execution_time_ms`, `domain`, `tool_name`, `data`, `visual_state`, `error`.
- Error object has exactly `type`, `message`, `recovery_suggestion`.
- Importing `agent_env_core` does not require optional browser/desktop dependencies.
- Package exports the three public async tool functions.
- Public async tool functions have docstrings covering inputs, returned schema, and handled failure behavior.

### Browser tests

Command:

```bash
python -m pytest tests/browser -m browser -q
```

Skips:

- Skip all browser tests if `playwright` import fails.
- Skip render tests if Chromium browser binaries are not installed.

Assertions:

- Valid URL returns `domain="browser"`, `tool_name="browser_navigate_and_render"`, non-empty `data.text_content`, and base64 JPEG `visual_state`.
- `wait_until` recorded as `networkidle`.
- JPEG width is `<= 1280` and format is `jpeg`.
- Invalid URL returns `success: false` and structured `ActionFailed` or validation error.
- Navigation timeout returns `success: false` with `TimeoutError`.
- `DEBUG_HEADED=1` selects headed mode through launch options.

### Desktop tests

Command:

```bash
python -m pytest tests/desktop -m desktop -q
```

Skips:

- Skip capture tests on CI or hosts without a graphical display.
- Skip Linux capture tests when only Wayland is available, except `test_wayland.py` which mocks this condition and must run everywhere.
- Skip backend-specific tests when running on a different real OS unless the test uses monkeypatching.

Assertions:

- Factory dispatch maps mocked platforms to correct backend classes.
- Wayland environment returns `WaylandUnsupportedError` with recovery suggestion.
- Successful capture returns screen dimensions, backend name, display server, and base64 JPEG visual state.
- Missing template image returns structured `TemplateImageError`.
- Template matching returns arrays shaped `[x, y, w, h, confidence]` and correct `match_count`.

### Terminal tests

Command:

```bash
python -m pytest tests/terminal -m terminal -q
```

Assertions:

- Safe command returns `success: true`, `exit_code: 0`, stdout/stderr strings, and truncation flags.
- Non-zero exit returns `success: false`, `error.type="CommandFailed"`, and preserves stdout/stderr in `data`.
- Empty or unparsable command returns `CommandParseError`.
- Shell syntax is not interpreted implicitly.
- Interactive prompt regex triggers `InteractivePromptException` and terminates the process.
- Timeout kills the process and returns `TimeoutError`.
- `timeout_sec > 300` is rejected before process launch.
- Each stream truncates at 10,000 characters and sets the matching truncation flag.
- Environment sanitizer strips `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, and `PYTHONPATH` unless override env is set.
- Destructive command handling is tested through the separate safety module without listing concrete destructive patterns in test code.

### Smoke tests

Command:

```bash
python -m pytest tests/smoke -m smoke -q
```

Assertions:

- Imports package.
- Calls terminal tool with a safe Python interpreter command.
- Calls browser tool with a local data URL or local test server URL if Playwright Chromium is installed; otherwise skips with a precise reason.
- Calls desktop tool with `template_image_path=None` if display is available; otherwise skips with a precise reason.
- Every returned object validates against the shared response schema.

### Plan-deliverable acceptance checks

Before implementation starts, verify the planning-only phase did not create code:

```bash
test -f .omo/plans/PLAN.md
test ! -d agent_env_core
test ! -d src/agent_env_core
```

The executor should also inspect `.omo/plans/PLAN.md` and confirm it contains the seven required sections from the build spec.

## 6. Phased Implementation Order

### Phase 1 — Packaging foundation

Done in this phase:

1. Create root packaging files: `pyproject.toml`, `README.md`, `LICENSE`.
2. Create `src/agent_env_core/__init__.py`, `py.typed`, `exceptions.py`, `response.py`, and `timing.py`.
3. Add tests for import behavior, exceptions, and shared response schema.
4. Run schema/import command:
   ```bash
   python -m pytest tests/test_response_schema.py tests/test_exceptions.py tests/test_package_import.py -q
   ```

Deferred:

- Browser, desktop, and terminal implementation internals.

### Phase 2 — Terminal tool and safety modules

Done in this phase:

1. Create terminal modules: `command.py`, `env.py`, `format_filesystem_blocklist.py`, `prompts.py`, `safety.py`, and `stream.py`.
2. Implement argv parsing and subprocess execution without shell execution.
3. Implement concurrent stdout/stderr streaming, prompt detection, timeout, truncation, and environment sanitization.
4. Implement destructive-command refusal by referencing the separate safety/blocklist module.
5. Add terminal tests.
6. Run:
   ```bash
   python -m pytest tests/terminal -m terminal -q
   ```

Deferred:

- Interactive shell sessions, PTY support, shell pipelines, and destructive-pattern documentation.

### Phase 3 — Browser navigate/render tool

Done in this phase:

1. Create browser modules: `render.py`, `screenshot.py`, and `stale_retry.py`.
2. Implement Playwright navigation with `wait_until="networkidle"`.
3. Implement `DEBUG_HEADED=1` launch behavior.
4. Extract text content, title, final URL, viewport metadata, JPEG screenshot, and base64 visual state.
5. Add browser tests with dependency/browser-binary skips.
6. Run:
   ```bash
   python -m pytest tests/browser -m browser -q
   ```

Deferred:

- Public click/type APIs, multi-page sessions, authentication helpers, downloads, tracing, and browser state persistence.

### Phase 4 — Desktop backend protocol and capture

Done in this phase:

1. Create desktop protocol, factory, capture orchestration, and OS backend files.
2. Implement macOS `screencapture`, Windows `mss`, and Linux/X11 `mss` capture paths.
3. Implement Wayland detection and structured unsupported error.
4. Add backend factory and capture tests with platform skips.
5. Run:
   ```bash
   python -m pytest tests/desktop/test_backend_factory.py tests/desktop/test_desktop_capture.py tests/desktop/test_wayland.py -q
   ```

Deferred:

- OCR, input automation, multi-monitor selection, and Wayland-native capture.

### Phase 5 — Desktop template matching

Done in this phase:

1. Implement OpenCV template matching in `desktop/locate.py`.
2. Validate template path handling and unreadable image behavior.
3. Return matches as `[x, y, w, h, confidence]` arrays.
4. Add matching tests.
5. Run:
   ```bash
   python -m pytest tests/desktop/test_template_matching.py -q
   ```

Deferred:

- Feature matching, OCR matching, object detection, and click helpers.

### Phase 6 — Smoke, quality, and cross-domain verification

Done in this phase:

1. Add smoke tests that import package and safely call each public tool.
2. Run all practical local tests:
   ```bash
   python -m pytest
   python -m ruff check .
   python -m mypy src/agent_env_core
   ```
3. Confirm platform skips are precise and not masking ordinary failures.
4. Confirm each public tool always returns the shared schema on success and handled failure.

Deferred:

- CI workflow files unless separately requested.

## 7. Explicit Non-Goals and Guardrails

- Do not write synchronous wrappers.
- Do not add public APIs beyond the three specified async functions.
- Do not add browser click/type public functions; keep stale-DOM retry private.
- Do not implement OCR behavior, even though `pytesseract` is present in optional desktop dependencies.
- Do not implement mouse or keyboard automation.
- Do not implement persistent terminal sessions, PTY mode, or shell execution.
- Do not enumerate destructive command patterns outside the dedicated safety/blocklist module.
- Do not make optional domain dependencies required for base package import.
- Do not silently clamp timeout values above 300 seconds; reject them with a structured error.

## 8. Open Questions

These are non-blocking because the plan sets defaults:

1. Logging: default is stdlib `logging`. If the user later prefers Loguru, add it as a runtime dependency and update logging calls consistently.
2. Version pins: exact pins are specified above. If installation fails on the executor platform, update only the failing pin and document the reason.
3. CI workflows: the spec requests tests and commands but not GitHub Actions or other CI configuration. CI files are deferred unless separately requested.
4. Wayland: first implementation fails clearly on Wayland as required. Native Wayland capture is deferred.
5. OCR: not implemented. Any OCR behavior requires a new spec because the requested desktop tool only captures and performs template matching.
