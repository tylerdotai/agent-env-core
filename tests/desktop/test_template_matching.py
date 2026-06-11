from io import BytesIO

import pytest

from agent_env_core.desktop.locate import locate_template
from agent_env_core.exceptions import TemplateImageError


def test_missing_template_raises_template_error(png_bytes, tmp_path):
    with pytest.raises(TemplateImageError):
        locate_template(png_bytes, str(tmp_path / "missing.png"))


def test_template_matching_returns_json_arrays(tmp_path):
    pytest.importorskip("cv2")
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    screen = Image.new("RGB", (60, 60), "black")
    ImageDraw.Draw(screen).rectangle((20, 20, 29, 29), fill="white")
    screen_out = BytesIO()
    screen.save(screen_out, format="PNG")
    template = tmp_path / "template.png"
    Image.new("RGB", (10, 10), "white").save(template)
    matches = locate_template(screen_out.getvalue(), str(template), threshold=0.8)
    assert matches
    assert len(matches[0]) == 5
    assert all(isinstance(value, int | float) for value in matches[0])
