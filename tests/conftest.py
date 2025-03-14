"""Shared fixtures. Real image files are generated here, never mocked."""

import io

import pytest
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()


def _noisy_image(width=640, height=480, seed=1):
    """An image with real detail, so lossy encoders actually have work to do.

    A flat-colour image compresses to almost nothing at every quality level,
    which would make the compressor's binary search meaningless in tests.
    """
    import random

    rng = random.Random(seed)
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        for x in range(width):
            px[x, y] = (
                (x * 7 + rng.randint(0, 80)) % 256,
                (y * 5 + rng.randint(0, 80)) % 256,
                (x * y // 13 + rng.randint(0, 80)) % 256,
            )
    return img


@pytest.fixture
def noisy_image():
    return _noisy_image


@pytest.fixture
def make_jpg(tmp_path):
    def _make(name="photo.jpg", width=640, height=480, quality=95):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _noisy_image(width, height).save(path, "JPEG", quality=quality)
        return path

    return _make


@pytest.fixture
def make_png(tmp_path):
    def _make(name="photo.png", width=320, height=240, mode="RGB"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        img = _noisy_image(width, height)
        if mode == "RGBA":
            img = img.convert("RGBA")
            # A genuinely varying alpha channel. A fully-opaque one gets
            # dropped by libwebp, which would make transparency tests vacuous.
            alpha = Image.linear_gradient("L").resize((width, height))
            img.putalpha(alpha)
        img.save(path, "PNG")
        return path

    return _make


@pytest.fixture
def make_heic(tmp_path):
    """A genuine HEIC file, encoded by libheif via pillow-heif."""

    def _make(name="shot.heic", width=640, height=480, exif=None):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        img = _noisy_image(width, height)
        kwargs = {"quality": 90}
        if exif is not None:
            kwargs["exif"] = exif
        img.save(path, "HEIF", **kwargs)
        return path

    return _make


@pytest.fixture
def exif_rotated_90():
    """EXIF bytes declaring Orientation=6 (rotate 90 CW on display)."""
    img = Image.new("RGB", (2, 2))
    exif = img.getexif()
    exif[274] = 6  # Orientation
    return exif.tobytes()


@pytest.fixture
def touch(tmp_path):
    def _touch(relpath, content=b"not an image"):
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    return _touch


@pytest.fixture
def exif_with_location():
    """EXIF as a phone writes it: camera, date, and GPS coordinates."""
    img = Image.new("RGB", (2, 2))
    exif = img.getexif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[0x0132] = "2026:09:21 14:00:00"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (14.0, 35.0, 0.0)
    gps[3], gps[4] = "E", (121.0, 0.0, 0.0)
    return exif.tobytes()


@pytest.fixture
def read_metadata():
    """(number of EXIF tags, number of GPS fields) in a written file."""

    def _read(path):
        with Image.open(path) as img:
            exif = img.getexif()
            gps = exif.get_ifd(0x8825)
            return len(exif), len(gps) if gps else 0

    return _read
