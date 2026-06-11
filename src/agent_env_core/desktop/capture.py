"""Async desktop capture and locate tool."""

import base64
from io import BytesIO

from agent_env_core.exceptions import DependencyMissingError
from agent_env_core.response import Response, make_response
from agent_env_core.timing import Timer

from .factory import display_server, get_desktop_backend
from .locate import locate_template


def _image_to_jpeg_base64(image_bytes: bytes) -> tuple[str, int, int]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise DependencyMissingError(
            "Pillow is required for desktop capture.", "Install agent-env-core[desktop]."
        ) from exc
    with Image.open(BytesIO(image_bytes)) as image:
        rgb = image.convert("RGB")
        output = BytesIO()
        rgb.save(output, format="JPEG", quality=70)
        return base64.b64encode(output.getvalue()).decode("ascii"), rgb.width, rgb.height


async def desktop_capture_and_locate(template_image_path: str | None = None) -> Response:
    """Capture the desktop, optionally locate a template, and return the shared schema.

    Args:
        template_image_path: Optional readable image path. When provided, OpenCV template matching
            returns JSON-compatible `[x, y, w, h, confidence]` arrays in screen-pixel coordinates.

    Returns:
        A dict with the shared envelope. `data` includes screen dimensions, backend, display server,
        template path, matches, match count, and coordinate system. `visual_state` is a base64 JPEG
        of the captured screen.

    Failure behavior:
        Unsupported platforms, Wayland-only Linux sessions, missing optional dependencies, capture
        failures, and template errors are caught and returned as structured errors.
    """
    timer = Timer()
    try:
        backend = get_desktop_backend()
        screen = backend.capture_screen()
        visual, width, height = _image_to_jpeg_base64(screen)
        matches = (
            locate_template(screen, template_image_path) if template_image_path is not None else []
        )
        data = {
            "screen_width": width,
            "screen_height": height,
            "backend": backend.name,
            "display_server": display_server(),
            "template_image_path": template_image_path,
            "matches": matches,
            "match_count": len(matches),
            "coordinate_system": "screen_pixels_origin_top_left",
        }
        return make_response(
            success=True,
            execution_time_ms=timer.elapsed_ms(),
            domain="desktop",
            tool_name="desktop_capture_and_locate",
            data=data,
            visual_state=visual,
        )
    except Exception as exc:
        return make_response(
            success=False,
            execution_time_ms=timer.elapsed_ms(),
            domain="desktop",
            tool_name="desktop_capture_and_locate",
            data={
                "screen_width": None,
                "screen_height": None,
                "backend": None,
                "display_server": None,
                "template_image_path": template_image_path,
                "matches": [],
                "match_count": 0,
                "coordinate_system": "screen_pixels_origin_top_left",
            },
            error=exc,
        )
