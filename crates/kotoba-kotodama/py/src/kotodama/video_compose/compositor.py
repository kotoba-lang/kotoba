"""Frame compositor: background + character + subtitle bar → PIL Image."""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

from .character import draw_character

W, H = 1280, 720
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/Library/Fonts/Arial Unicode MS.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _FONT_CACHE:
        for path in _FONT_CANDIDATES:
            if os.path.exists(path):
                try:
                    _FONT_CACHE[size] = ImageFont.truetype(path, size)
                    break
                except Exception:
                    pass
        if size not in _FONT_CACHE:
            _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]


def _gradient_bg(location: str = "") -> Image.Image:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(100 + 100 * (1 - t))
        g = int(150 + 80 * (1 - t))
        b = int(220 + 35 * (1 - t))
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    # location hint in top-right corner
    if location:
        draw.text((W - 10, 10), location, font=_font(20), fill=(255, 255, 255, 180),
                  anchor="ra")
    return img


def compose_frame(
    speaker: str,
    text: str,
    location: str = "",
    emotion: str = "normal",
    bg_image: Image.Image | None = None,
) -> Image.Image:
    """Compose a single 1280×720 frame.

    Args:
        speaker: "left" (ゆきり) or "right" (まりり)
        text: dialogue text for subtitle bar
        location: scene background hint (shown in top-right)
        emotion: normal | happy | surprised | sad | angry
        bg_image: optional PIL Image to use as background (resized to 1280×720)

    Returns:
        PIL Image (RGB, 1280×720)
    """
    if bg_image is not None:
        frame = bg_image.convert("RGB").resize((W, H))
    else:
        frame = _gradient_bg(location)

    draw = ImageDraw.Draw(frame)

    # Characters sit in the lower third so the AI background is prominent
    char_y = H - 180
    if speaker == "left":
        draw_character(draw, "left", W // 4, char_y, size=220, emotion=emotion)
        # dim the non-speaking side slightly
        overlay = Image.new("RGBA", (W // 2, H), (0, 0, 0, 40))
        frame.paste(Image.new("RGB", (W // 2, H), (0, 0, 0)), (W // 2, 0),
                    mask=overlay.split()[3])
    else:
        draw_character(draw, "right", 3 * W // 4, char_y, size=220, emotion=emotion)
        overlay = Image.new("RGBA", (W // 2, H), (0, 0, 0, 40))
        frame.paste(Image.new("RGB", (W // 2, H), (0, 0, 0)), (0, 0),
                    mask=overlay.split()[3])

    # subtitle bar — taller for readability (130 px)
    bar_h = 130
    bar = Image.new("RGBA", (W, bar_h), (0, 0, 0, 200))
    bar_rgb = bar.convert("RGB")
    frame.paste(bar_rgb, (0, H - bar_h), mask=bar.split()[3])

    # speaker label + dialogue text with drop-shadow for contrast
    label = "ゆきり" if speaker == "left" else "まりり"
    label_color = (255, 200, 80) if speaker == "left" else (100, 220, 255)
    shadow = (0, 0, 0)
    label_y = H - bar_h + 10
    text_y = H - bar_h + 44

    # shadow offset +2 px for both label and dialogue
    draw.text((22, label_y + 2), label, font=_font(24), fill=shadow)
    draw.text((20, label_y), label, font=_font(24), fill=label_color)
    draw.text((22, text_y + 2), text, font=_font(32), fill=shadow)
    draw.text((20, text_y), text, font=_font(32), fill=(255, 255, 255))

    return frame
