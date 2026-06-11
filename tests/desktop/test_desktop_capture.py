import base64

import pytest

from agent_env_core.desktop import capture


class FakeBackend:
    name = "fake"

    def __init__(self, png_bytes):
        self.png_bytes = png_bytes

    def capture_screen(self):
        return self.png_bytes

    def screen_size(self):
        return (40, 40)


@pytest.mark.desktop
@pytest.mark.asyncio
async def test_desktop_capture_returns_dimensions_and_visual(
    monkeypatch, png_bytes, response_schema
):
    monkeypatch.setattr(capture, "get_desktop_backend", lambda: FakeBackend(png_bytes))
    monkeypatch.setattr(capture, "display_server", lambda: "test-display")
    response = await capture.desktop_capture_and_locate()
    response_schema(response)
    assert response["success"]
    assert response["data"]["screen_width"] == 40
    assert response["data"]["backend"] == "fake"
    assert response["data"]["match_count"] == 0
    assert base64.b64decode(response["visual_state"].encode("ascii"))
