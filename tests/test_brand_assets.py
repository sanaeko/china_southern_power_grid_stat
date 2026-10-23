"""Tests for the integration brand assets.

Home Assistant serves integration branding from ``<integration>/brand/`` when
the filenames match its allow-list, so a missing or misnamed file shows up as a
broken/blank logo in the integrations list. These tests lock that contract down.
"""

from __future__ import annotations

import os

import pytest

PIL = pytest.importorskip("PIL", reason="Pillow is needed to verify the images")
from PIL import Image  # noqa: E402

BRAND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "china_southern_power_grid_stat",
    "brand",
)

# Mirrors homeassistant/components/brands/const.py ALLOWED_IMAGES.
ALLOWED_IMAGES = {
    "icon.png",
    "logo.png",
    "icon@2x.png",
    "logo@2x.png",
    "dark_icon.png",
    "dark_logo.png",
    "dark_icon@2x.png",
    "dark_logo@2x.png",
}

# Home Assistant requests these for a normal (light) integration card.
REQUIRED_FOR_DISPLAY = {"icon.png", "logo.png"}


def test_brand_directory_exists():
    """`has_branding` requires a `brand` entry at the integration root."""
    assert os.path.isdir(BRAND_DIR), f"missing brand directory: {BRAND_DIR}"


def test_all_generated_names_are_allowed():
    """Every file must be a name HA will actually serve."""
    present = {f for f in os.listdir(BRAND_DIR) if f.endswith(".png")}
    assert present, "no brand images found"
    unexpected = present - ALLOWED_IMAGES
    assert not unexpected, f"HA would never serve these files: {sorted(unexpected)}"


def test_required_images_present():
    present = {f for f in os.listdir(BRAND_DIR)}
    missing = REQUIRED_FOR_DISPLAY - present
    assert not missing, f"logo would not display, missing: {sorted(missing)}"


@pytest.mark.parametrize("name", sorted(ALLOWED_IMAGES))
def test_image_is_a_valid_png(name):
    path = os.path.join(BRAND_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated")
    with Image.open(path) as im:
        assert im.format == "PNG", f"{name} is {im.format}, not PNG"
        assert im.width > 0 and im.height > 0


def test_icon_is_square_and_uses_expected_scale():
    """Icons must be square; the @2x variant is twice the 1x size."""
    with Image.open(os.path.join(BRAND_DIR, "icon.png")) as one:
        with Image.open(os.path.join(BRAND_DIR, "icon@2x.png")) as two:
            assert one.width == one.height
            assert two.width == two.height
            assert two.width == one.width * 2


def test_logo_is_wider_than_tall():
    """A logo is a horizontal wordmark, not a square."""
    with Image.open(os.path.join(BRAND_DIR, "logo.png")) as im:
        assert im.width > im.height * 2, (
            f"logo should be wide, got {im.width}x{im.height}"
        )


def test_images_have_transparency():
    """Brand images are drawn on transparent backgrounds."""
    with Image.open(os.path.join(BRAND_DIR, "icon.png")) as im:
        assert im.mode == "RGBA", f"expected RGBA, got {im.mode}"
        alpha = im.getchannel("A")
        assert alpha.getextrema()[0] == 0, "icon has no transparent pixels"


def test_icon_contains_the_accent_colour():
    """The lightning accent should be present, proving the art rendered."""
    with Image.open(os.path.join(BRAND_DIR, "icon.png")).convert("RGBA") as im:
        colours = im.getcolors(maxcolors=1_000_000) or []
    accents = [
        count
        for count, (r, g, b, a) in colours
        if a > 200 and r > 200 and g > 150 and b < 130
    ]
    assert sum(accents) > 100, "accent (yellow) pixels missing from the icon"