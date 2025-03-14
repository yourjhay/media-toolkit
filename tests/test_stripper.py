"""The stripper's whole promise is that the picture is untouched.

Every test that matters here compares the decoded pixels before and after.
Anything that re-encodes would pass a "metadata is gone" check while quietly
degrading the image, which is the failure this tool exists to avoid.
"""

import hashlib
import io

import pytest
from PIL import Image

from image_toolkit.stripper import (
    STRIP_ALL,
    STRIP_LOCATION,
    UnsupportedFormat,
    strip_bytes,
)


def _pixels(data: bytes) -> str:
    with Image.open(io.BytesIO(data)) as img:
        return hashlib.sha256(img.convert("RGBA").tobytes()).hexdigest()


def _meta(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as img:
        exif = img.getexif()
        gps = exif.get_ifd(0x8825)
        return len(exif), len(gps) if gps else 0


@pytest.fixture
def photo():
    """A detailed image, so any re-encoding would change the pixels."""
    img = Image.new("RGB", (240, 180))
    px = img.load()
    for y in range(180):
        for x in range(240):
            px[x, y] = ((x * 7) % 256, (y * 11) % 256, (x * y) % 256)
    return img


@pytest.fixture
def located_exif():
    img = Image.new("RGB", (2, 2))
    exif = img.getexif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[0x0132] = "2026:09:21 14:00:00"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (14.0, 35.0, 30.0)
    gps[3], gps[4] = "E", (121.0, 0.0, 0.0)
    return exif.tobytes()


def _encode(photo, fmt, exif=None, **kw):
    buf = io.BytesIO()
    photo.save(buf, fmt, **({"exif": exif} if exif else {}), **kw)
    return buf.getvalue()


# --- JPEG ------------------------------------------------------------------

def test_jpeg_pixels_are_untouched(photo, located_exif):
    data = _encode(photo, "JPEG", located_exif, quality=95)

    stripped = strip_bytes(data, ".jpg", STRIP_ALL)

    assert _pixels(stripped) == _pixels(data)


def test_jpeg_metadata_is_gone(photo, located_exif):
    data = _encode(photo, "JPEG", located_exif, quality=95)

    assert _meta(strip_bytes(data, ".jpg", STRIP_ALL)) == (0, 0)


def test_jpeg_gets_smaller(photo, located_exif):
    data = _encode(photo, "JPEG", located_exif, quality=95)

    assert len(strip_bytes(data, ".jpg", STRIP_ALL)) < len(data)


def test_jpeg_location_only_keeps_the_camera(photo, located_exif):
    data = _encode(photo, "JPEG", located_exif, quality=95)

    stripped = strip_bytes(data, ".jpg", STRIP_LOCATION)

    tags, gps = _meta(stripped)
    assert gps == 0
    assert tags > 0
    assert _pixels(stripped) == _pixels(data)
    with Image.open(io.BytesIO(stripped)) as img:
        assert img.getexif().get(0x0110) == "iPhone 15 Pro"


def test_jpeg_colour_profile_survives(photo):
    """Dropping the ICC profile would visibly shift the colours."""
    profile = b"\x00\x00\x02\x0cICC_FAKE" + b"\x00" * 500
    data = _encode(photo, "JPEG", quality=95, icc_profile=profile)

    stripped = strip_bytes(data, ".jpg", STRIP_ALL)

    with Image.open(io.BytesIO(stripped)) as img:
        assert img.info.get("icc_profile") == profile


def test_stripping_a_jpeg_with_no_metadata_changes_nothing(photo):
    data = _encode(photo, "JPEG", quality=95)

    assert strip_bytes(data, ".jpg", STRIP_ALL) == data


# --- PNG -------------------------------------------------------------------

def test_png_pixels_are_untouched(photo, located_exif):
    data = _encode(photo, "PNG", located_exif)

    stripped = strip_bytes(data, ".png", STRIP_ALL)

    assert _pixels(stripped) == _pixels(data)


def test_png_metadata_is_gone(photo, located_exif):
    data = _encode(photo, "PNG", located_exif)

    assert _meta(strip_bytes(data, ".png", STRIP_ALL)) == (0, 0)


def test_png_text_chunks_are_removed(photo):
    from PIL import PngImagePlugin

    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "taken at home")
    buf = io.BytesIO()
    photo.save(buf, "PNG", pnginfo=info)
    data = buf.getvalue()

    stripped = strip_bytes(data, ".png", STRIP_ALL)

    assert b"taken at home" not in stripped
    assert _pixels(stripped) == _pixels(data)


def test_png_transparency_survives(located_exif):
    img = Image.new("RGBA", (64, 64), (200, 100, 50, 0))
    for y in range(64):
        for x in range(64):
            img.putpixel((x, y), (x * 4 % 256, y * 4 % 256, 120, x * 4 % 256))
    buf = io.BytesIO()
    img.save(buf, "PNG", exif=located_exif)
    data = buf.getvalue()

    stripped = strip_bytes(data, ".png", STRIP_ALL)

    assert _pixels(stripped) == _pixels(data)
    with Image.open(io.BytesIO(stripped)) as out:
        assert out.mode == "RGBA"


def test_png_location_only_keeps_the_camera(photo, located_exif):
    data = _encode(photo, "PNG", located_exif)

    stripped = strip_bytes(data, ".png", STRIP_LOCATION)

    tags, gps = _meta(stripped)
    assert gps == 0 and tags > 0
    assert _pixels(stripped) == _pixels(data)


# --- WebP ------------------------------------------------------------------

def test_webp_pixels_are_untouched(photo, located_exif):
    data = _encode(photo, "WEBP", located_exif, quality=90)

    stripped = strip_bytes(data, ".webp", STRIP_ALL)

    assert _pixels(stripped) == _pixels(data)


def test_webp_metadata_is_gone(photo, located_exif):
    data = _encode(photo, "WEBP", located_exif, quality=90)

    assert _meta(strip_bytes(data, ".webp", STRIP_ALL)) == (0, 0)


def test_webp_stays_a_valid_riff_file(photo, located_exif):
    data = _encode(photo, "WEBP", located_exif, quality=90)

    stripped = strip_bytes(data, ".webp", STRIP_ALL)

    assert stripped[:4] == b"RIFF"
    assert stripped[8:12] == b"WEBP"
    declared = int.from_bytes(stripped[4:8], "little")
    assert declared == len(stripped) - 8, "the RIFF size header must be rewritten"


# --- error handling --------------------------------------------------------

def test_an_unsupported_format_is_refused(photo):
    data = _encode(photo, "GIF")

    with pytest.raises(UnsupportedFormat):
        strip_bytes(data, ".gif", STRIP_ALL)


def test_rubbish_input_raises_rather_than_producing_rubbish_output():
    with pytest.raises(Exception):
        strip_bytes(b"this is not an image at all", ".jpg", STRIP_ALL)


def test_an_unknown_mode_is_rejected(photo):
    with pytest.raises(ValueError):
        strip_bytes(_encode(photo, "JPEG"), ".jpg", "whatever")
