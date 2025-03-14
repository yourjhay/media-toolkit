import hashlib

import pytest
from PIL import Image

from image_toolkit.core import strip_metadata
from image_toolkit.stripper import STRIP_ALL, STRIP_LOCATION


def _pixels(path):
    with Image.open(path) as img:
        return hashlib.sha256(img.convert("RGBA").tobytes()).hexdigest()


def _gps_fields(path):
    with Image.open(path) as img:
        gps = img.getexif().get_ifd(0x8825)
        return len(gps) if gps else 0


def test_it_removes_the_metadata_without_touching_the_picture(
    make_jpg, exif_with_location, tmp_path
):
    src = make_jpg("photo.jpg", width=400, height=300, quality=95)
    with Image.open(src) as img:
        img.save(src, "JPEG", quality=95, exif=exif_with_location)
    before = _pixels(src)

    result = strip_metadata(src, tmp_path / "out", mode=STRIP_ALL)

    assert result.status == "ok"
    assert _gps_fields(result.output) == 0
    assert _pixels(result.output) == before, "the picture must be untouched"


def test_location_only_mode_keeps_the_camera(make_jpg, exif_with_location, tmp_path):
    src = make_jpg("photo.jpg", width=400, height=300, quality=95)
    with Image.open(src) as img:
        img.save(src, "JPEG", quality=95, exif=exif_with_location)
    before = _pixels(src)

    result = strip_metadata(src, tmp_path / "out", mode=STRIP_LOCATION)

    assert _gps_fields(result.output) == 0
    with Image.open(result.output) as img:
        assert img.getexif().get(0x0110) == "iPhone 15 Pro"
    assert _pixels(result.output) == before


def test_the_result_says_how_many_bytes_of_metadata_went(
    make_jpg, exif_with_location, tmp_path
):
    src = make_jpg("photo.jpg", width=400, height=300, quality=95)
    with Image.open(src) as img:
        img.save(src, "JPEG", quality=95, exif=exif_with_location)

    result = strip_metadata(src, tmp_path / "out", mode=STRIP_ALL)

    assert result.output_bytes < result.source_bytes
    assert "metadata" in result.detail.lower()


def test_a_file_with_nothing_to_remove_says_so(make_jpg, tmp_path):
    src = make_jpg("plain.jpg")

    result = strip_metadata(src, tmp_path / "out", mode=STRIP_ALL)

    assert result.status == "ok"
    assert "no metadata" in result.detail.lower()
    assert result.output.read_bytes() == src.read_bytes()


def test_it_refuses_to_write_over_the_source(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    original = src.read_bytes()

    result = strip_metadata(src, src.parent, mode=STRIP_ALL)

    assert result.status == "failed"
    assert src.read_bytes() == original


def test_existing_output_is_left_alone_by_default(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "photo.jpg").write_bytes(b"keep me")

    result = strip_metadata(src, out_dir, mode=STRIP_ALL)

    assert result.status == "skipped"
    assert (out_dir / "photo.jpg").read_bytes() == b"keep me"


def test_a_format_it_cannot_edit_is_reported_not_raised(make_heic, tmp_path):
    """HEIC containers are not handled; that is one file's problem, not a crash."""
    result = strip_metadata(make_heic("shot.heic"), tmp_path / "out", mode=STRIP_ALL)

    assert result.status == "failed"
    assert "heic" in result.detail.lower() or "strip" in result.detail.lower()


def test_a_corrupt_file_is_reported_not_raised(touch, tmp_path):
    result = strip_metadata(touch("broken.jpg", b"not a jpeg"), tmp_path / "out")

    assert result.status == "failed"
    assert result.detail


def test_an_unknown_mode_is_rejected_up_front(make_jpg, tmp_path):
    with pytest.raises(ValueError):
        strip_metadata(make_jpg("photo.jpg"), tmp_path / "out", mode="whatever")
