import base64
from io import BytesIO

import pytest


def assert_response_schema(response):
    assert set(response) == {
        "success",
        "execution_time_ms",
        "domain",
        "tool_name",
        "data",
        "visual_state",
        "error",
    }
    assert set(response["error"]) == {"type", "message", "recovery_suggestion"}


@pytest.fixture
def response_schema():
    return assert_response_schema


@pytest.fixture
def png_bytes():
    pytest.importorskip("PIL")
    from PIL import Image

    image = Image.new("RGB", (40, 40), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def template_image(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    path = tmp_path / "template.png"
    Image.new("RGB", (10, 10), "white").save(path)
    return path


def is_base64(value):
    base64.b64decode(value.encode("ascii"), validate=True)
    return True
