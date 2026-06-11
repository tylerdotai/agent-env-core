"""Template matching helpers."""

from pathlib import Path

from agent_env_core.exceptions import DependencyMissingError, TemplateImageError

Match = list[int | float]


def locate_template(
    screen_bytes: bytes, template_image_path: str, threshold: float = 0.8
) -> list[Match]:
    """Locate template occurrences in screenshot bytes as [x, y, w, h, confidence]."""
    path = Path(template_image_path)
    if not path.is_file():
        raise TemplateImageError("Template image does not exist.", "Pass a readable image path.")
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise DependencyMissingError(
            "OpenCV and NumPy are required for template matching.",
            "Install agent-env-core[desktop].",
        ) from exc
    template_data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    template = cv2.imdecode(template_data, cv2.IMREAD_COLOR)
    if template is None:
        raise TemplateImageError(
            "Template image could not be decoded.", "Pass a readable image path."
        )
    screen_data = np.frombuffer(screen_bytes, dtype=np.uint8)
    screen = cv2.imdecode(screen_data, cv2.IMREAD_COLOR)
    if screen is None:
        raise TemplateImageError("Captured screen could not be decoded.", "Retry screen capture.")
    h, w = template.shape[:2]
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= threshold)
    candidates = sorted(
        (
            [int(x), int(y), int(w), int(h), float(result[y, x])]
            for y, x in zip(ys, xs, strict=True)
        ),
        key=lambda item: item[4],
        reverse=True,
    )
    matches: list[Match] = []
    for candidate in candidates:
        if not any(_overlaps(candidate, existing) for existing in matches):
            matches.append(candidate)
    return matches


def _overlaps(a: Match, b: Match) -> bool:
    ax, ay, aw, ah, _ = a
    bx, by, bw, bh, _ = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return False
    inter = (right - left) * (bottom - top)
    return inter / min(aw * ah, bw * bh) > 0.5
