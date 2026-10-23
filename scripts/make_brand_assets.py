"""Generate brand assets (icon/logo) for the integration.

The CSG brand colours are a deep blue-green with a lightning motif, matching
the "electricity" nature of the integration. Everything is drawn with Pillow at
4x and downsampled, so edges stay crisp at the sizes Home Assistant uses.

Outputs into <integration>/brand/:
  icon.png / icon@2x.png        square app-style icon (1x and 2x)
  logo.png / logo@2x.png        wide logo on transparent background
  dark_icon.png                 icon variant for dark themes
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND_DIR = os.path.join(
    HERE, "custom_components", "china_southern_power_grid_stat", "brand"
)

# CSG-ish palette: deep blue-green gradient + a bright lightning accent.
TOP = (0, 82, 147)  # #005293
BOTTOM = (0, 132, 137)  # #008489
ACCENT = (255, 214, 64)  # #FFD640
ACCENT_DARK = (255, 168, 0)  # #FFA800

SS = 4  # supersampling factor


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def _vertical_gradient(size: int, top, bottom) -> Image.Image:
    img = Image.new("RGBA", (1, size))
    for y in range(size):
        img.putpixel((0, y), (*_lerp(top, bottom, y / max(1, size - 1)), 255))
    return img.resize((size, size))


def _rounded_mask(size: int, radius_ratio: float) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    pad = int(size * 0.04)
    r = int(size * radius_ratio)
    draw.rounded_rectangle((pad, pad, size - pad, size - pad), radius=r, fill=255)
    return mask


def draw_bolt(draw: ImageDraw.ImageDraw, cx: float, cy: float, h: float, color):
    """Draw a thick lightning bolt centred at (cx, cy) with total height h."""
    w = h * 0.62
    # Bolt polygon in a unit box, then scaled.
    points = [
        (0.56, 0.00),
        (0.16, 0.56),
        (0.44, 0.56),
        (0.34, 1.00),
        (0.84, 0.40),
        (0.54, 0.40),
        (0.66, 0.00),
    ]
    ox = cx - w / 2
    oy = cy - h / 2
    poly = [(ox + px * w, oy + py * h) for px, py in points]
    draw.polygon(poly, fill=color)


def make_icon(size: int, dark: bool = False) -> Image.Image:
    """Create the square icon at ``size`` px (already downsampled)."""
    big = size * SS
    top = (18, 26, 40) if dark else TOP
    bottom = (28, 48, 62) if dark else BOTTOM

    bg = _vertical_gradient(big, top, bottom).convert("RGBA")

    # Subtle radial glow behind the bolt for depth.
    glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for i in range(12, 0, -1):
        radius = big * 0.10 * i
        alpha = int(6 * i * 0.55)
        gdraw.ellipse(
            (big / 2 - radius, big / 2 - radius, big / 2 + radius, big / 2 + radius),
            fill=(255, 255, 255, alpha),
        )
    bg.alpha_composite(glow)

    draw = ImageDraw.Draw(bg)
    bolt_h = big * 0.60
    # Accent shadow offset then the bolt itself.
    draw_bolt(draw, big / 2 + big * 0.012, big / 2 + big * 0.012, bolt_h, ACCENT_DARK)
    draw_bolt(draw, big / 2, big / 2, bolt_h, ACCENT)

    # A thin meter-ring arc to hint at a smart meter.
    ring_r = big * 0.335
    box = (big / 2 - ring_r, big / 2 - ring_r, big / 2 + ring_r, big / 2 + ring_r)
    draw.arc(box, start=205, end=335, fill=(255, 255, 255, 90), width=max(2, big // 90))
    draw.arc(box, start=25, end=155, fill=(255, 255, 255, 90), width=max(2, big // 90))

    mask = _rounded_mask(big, 0.22)
    bg.putalpha(mask)

    return bg.resize((size, size), Image.LANCZOS)


def make_logo(width: int, dark: bool = False) -> Image.Image:
    """Create the wide logo (icon mark + wordmark block) at ``width`` px."""
    big_w = width * SS
    height = int(big_w / 3.0)
    img = Image.new("RGBA", (big_w, height), (0, 0, 0, 0))

    # Icon mark on the left, rounded square with gradient.
    mark = int(height * 0.86)
    top = (18, 26, 40) if dark else TOP
    bottom = (28, 48, 62) if dark else BOTTOM
    mark_img = _vertical_gradient(mark, top, bottom).convert("RGBA")
    mdraw = ImageDraw.Draw(mark_img)
    draw_bolt(mdraw, mark / 2, mark / 2, mark * 0.60, ACCENT)
    mask = Image.new("L", (mark, mark), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, mark - 1, mark - 1), radius=int(mark * 0.22), fill=255
    )
    mark_img.putalpha(mask)
    img.alpha_composite(mark_img, (int(height * 0.07), int((height - mark) / 2)))

    # Wordmark: bars representing "stats" next to the bolt, keeps it text-free
    # so no font is required and it renders identically everywhere. The bars are
    # laid out to fill the width left over after the icon mark.
    d = ImageDraw.Draw(img)
    text_color = (255, 255, 255, 255) if not dark else (235, 240, 248, 255)

    pad = int(height * 0.07)
    bar_start = int(height * 0.07) + mark + int(height * 0.30)
    bar_end = big_w - pad
    count = 5
    gap = int(height * 0.10)
    bar_w = max(3, (bar_end - bar_start - gap * (count - 1)) // count)

    heights = [0.26, 0.44, 0.62, 0.36, 0.52]
    bar_area_h = height * 0.56
    for i, hf in enumerate(heights):
        bh = int(bar_area_h * hf)
        x0 = bar_start + i * (bar_w + gap)
        y1 = int(height * 0.50 + bar_area_h / 2)
        y0 = y1 - bh
        color = ACCENT if i == 2 else text_color
        d.rounded_rectangle((x0, y0, x0 + bar_w, y1), radius=bar_w // 3, fill=color)

    return img.resize((width, height // SS), Image.LANCZOS)


def _save(image: Image.Image, name: str) -> None:
    """Write a PNG, optimised, to the brand directory."""
    path = os.path.join(BRAND_DIR, name)
    image.save(path, format="PNG", optimize=True)
    print(f"{name:20} {image.size[0]}x{image.size[1]}  {os.path.getsize(path)} bytes")


def main() -> None:
    os.makedirs(BRAND_DIR, exist_ok=True)

    _save(make_icon(256), "icon.png")
    _save(make_icon(512), "icon@2x.png")
    _save(make_icon(256, dark=True), "dark_icon.png")
    _save(make_icon(512, dark=True), "dark_icon@2x.png")

    _save(make_logo(512), "logo.png")
    _save(make_logo(1024), "logo@2x.png")
    _save(make_logo(512, dark=True), "dark_logo.png")
    _save(make_logo(1024, dark=True), "dark_logo@2x.png")


if __name__ == "__main__":
    main()
