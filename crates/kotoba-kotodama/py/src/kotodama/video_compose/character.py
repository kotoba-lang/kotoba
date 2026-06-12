"""PIL character drawing for ゆきり (left/Reimu-like) and まりり (right/Marisa-like)."""

from __future__ import annotations

from PIL import ImageDraw


def draw_character(
    draw: ImageDraw.ImageDraw,
    side: str,
    cx: int,
    cy: int,
    size: int = 220,
    emotion: str = "normal",
) -> None:
    """Draw a yukkuri character at (cx, cy) with given emotion.

    Args:
        side: "left" → ゆきり (Reimu-like), "right" → まりり (Marisa-like)
        emotion: normal | happy | surprised | sad | angry
    """
    if side == "left":
        _draw_reimu(draw, cx, cy, size, emotion)
    else:
        _draw_marisa(draw, cx, cy, size, emotion)


def _eyes(draw: ImageDraw.ImageDraw, cx: int, eye_y: int, emotion: str, color: tuple):
    if emotion == "happy":
        draw.arc([cx - 28, eye_y - 8, cx - 12, eye_y + 2], 200, 340, fill=color, width=3)
        draw.arc([cx + 12, eye_y - 8, cx + 28, eye_y + 2], 200, 340, fill=color, width=3)
    elif emotion in ("surprised", "angry"):
        draw.ellipse([cx - 28, eye_y - 10, cx - 10, eye_y + 8], fill=color)
        draw.ellipse([cx + 10, eye_y - 10, cx + 28, eye_y + 8], fill=color)
    else:
        draw.ellipse([cx - 26, eye_y - 6, cx - 12, eye_y + 4], fill=color)
        draw.ellipse([cx + 12, eye_y - 6, cx + 26, eye_y + 4], fill=color)


def _mouth(draw: ImageDraw.ImageDraw, cx: int, mouth_y: int, emotion: str):
    if emotion in ("happy", "surprised"):
        draw.arc([cx - 12, mouth_y - 5, cx + 12, mouth_y + 10], 10, 170,
                 fill=(150, 80, 80), width=2)
    elif emotion == "sad":
        draw.arc([cx - 12, mouth_y, cx + 12, mouth_y + 15], 190, 350,
                 fill=(150, 80, 80), width=2)
    else:
        draw.line([cx - 8, mouth_y + 3, cx + 8, mouth_y + 3], fill=(150, 80, 80), width=2)


def _draw_reimu(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, emotion: str):
    r = size // 3
    # body (white + red skirt)
    draw.ellipse([cx - size // 3, cy - size // 6, cx + size // 3, cy + size // 2],
                 fill=(255, 250, 250))
    draw.rectangle([cx - size // 3, cy + size // 6, cx + size // 3, cy + size // 2],
                   fill=(200, 30, 30), outline=(160, 20, 20))
    # head
    draw.ellipse([cx - r, cy - size // 2, cx + r, cy], fill=(255, 220, 180))
    # hair (dark brown)
    draw.ellipse([cx - r, cy - size // 2 - 10, cx + r, cy - size // 4], fill=(40, 20, 20))
    # red bow
    bow_y = cy - size // 2 - 15
    draw.polygon([(cx - 25, bow_y), (cx, bow_y - 15), (cx + 25, bow_y), (cx, bow_y + 10)],
                 fill=(200, 30, 30))
    _eyes(draw, cx, cy - size // 3, emotion, (30, 30, 30))
    _mouth(draw, cx, cy - size // 6, emotion)


def _draw_marisa(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, emotion: str):
    r = size // 3
    # body (black + yellow apron)
    draw.ellipse([cx - size // 3, cy - size // 6, cx + size // 3, cy + size // 2],
                 fill=(40, 40, 50))
    draw.polygon([(cx - 20, cy - size // 6), (cx, cy - size // 6 - 20), (cx + 20, cy - size // 6)],
                 fill=(220, 190, 50))
    draw.rectangle([cx - size // 4, cy + size // 8, cx + size // 4, cy + size // 2],
                   fill=(215, 185, 45))
    # head
    draw.ellipse([cx - r, cy - size // 2, cx + r, cy], fill=(255, 220, 180))
    # blonde hair
    draw.ellipse([cx - r - 5, cy - size // 2, cx + r + 5, cy - size // 5], fill=(220, 185, 60))
    # witch hat
    hat_base_y = cy - size // 2 + 5
    draw.polygon([(cx - r - 10, hat_base_y), (cx, cy - size - 20), (cx + r + 10, hat_base_y)],
                 fill=(20, 20, 30))
    draw.ellipse([cx - r - 15, hat_base_y - 8, cx + r + 15, hat_base_y + 8], fill=(30, 30, 40))
    draw.rectangle([cx - r - 10, hat_base_y - 5, cx + r + 10, hat_base_y + 2], fill=(200, 170, 40))
    _eyes(draw, cx, cy - size // 3, emotion, (80, 60, 20))
    _mouth(draw, cx, cy - size // 6, emotion)
