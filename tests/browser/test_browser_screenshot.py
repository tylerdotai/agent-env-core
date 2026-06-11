import base64

import pytest

from agent_env_core.browser.screenshot import screenshot_png_to_jpeg_base64


@pytest.mark.browser
def test_screenshot_jpeg_output_is_base64_and_bounded():
    pytest.importorskip("PIL")
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (1400, 700), "blue")
    output = BytesIO()
    image.save(output, format="PNG")
    encoded, width, height, fmt = screenshot_png_to_jpeg_base64(output.getvalue())
    assert width == 1280
    assert height == 640
    assert fmt == "jpeg"
    assert base64.b64decode(encoded.encode("ascii"))
