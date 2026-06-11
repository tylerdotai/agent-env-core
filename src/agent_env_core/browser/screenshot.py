"""Browser screenshot conversion helpers."""

import base64
from io import BytesIO

from agent_env_core.exceptions import DependencyMissingError

MAX_WIDTH = 1280
JPEG_QUALITY = 70


def screenshot_png_to_jpeg_base64(png_bytes: bytes) -> tuple[str, int, int, str]:
    """Convert PNG screenshot bytes to downsampled base64 JPEG."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise DependencyMissingError(
            "Pillow is required for browser screenshots.",
            "Install agent-env-core[browser].",
        ) from exc
    with Image.open(BytesIO(png_bytes)) as image:
        rgb = image.convert("RGB")
        if rgb.width > MAX_WIDTH:
            height = round(rgb.height * (MAX_WIDTH / rgb.width))
            rgb = rgb.resize((MAX_WIDTH, height))
        output = BytesIO()
        rgb.save(output, format="JPEG", quality=JPEG_QUALITY)
        return base64.b64encode(output.getvalue()).decode("ascii"), rgb.width, rgb.height, "jpeg"
