import pytest

from image_toolkit.core import KEEP, SAFE, STRIP, compress, convert_heic, convert_to_webp


def test_stripping_removes_everything(make_heic, exif_with_location, read_metadata, tmp_path):
    src = make_heic("phone.heic", exif=exif_with_location)

    result = convert_heic(src, tmp_path / "out", fmt="jpg", metadata=STRIP)

    assert read_metadata(result.output) == (0, 0)


def test_safe_keeps_the_camera_and_date_but_drops_the_location(
    make_heic, exif_with_location, read_metadata, tmp_path
):
    """The point of the mode: useful for your archive, safe to share."""
    from PIL import Image

    src = make_heic("phone.heic", exif=exif_with_location)

    result = convert_heic(src, tmp_path / "out", fmt="jpg", metadata=SAFE)

    tags, gps = read_metadata(result.output)
    assert gps == 0, "location must not survive"
    assert tags > 0, "camera and date should survive"
    with Image.open(result.output) as img:
        assert img.getexif().get(0x0110) == "iPhone 15 Pro"


def test_keep_preserves_the_location_when_explicitly_asked(
    make_heic, exif_with_location, read_metadata, tmp_path
):
    src = make_heic("phone.heic", exif=exif_with_location)

    result = convert_heic(src, tmp_path / "out", fmt="jpg", metadata=KEEP)

    assert read_metadata(result.output)[1] > 0


def test_location_is_dropped_by_default(make_heic, exif_with_location, read_metadata, tmp_path):
    """The default must be the safe one; a leak should take a deliberate choice."""
    src = make_heic("phone.heic", exif=exif_with_location)

    result = convert_heic(src, tmp_path / "out", fmt="jpg")

    assert read_metadata(result.output)[1] == 0


def test_webp_honours_the_metadata_choice(
    make_heic, exif_with_location, read_metadata, tmp_path
):
    src = make_heic("phone.heic", exif=exif_with_location)

    kept = convert_to_webp(src, tmp_path / "keep", metadata=KEEP)
    stripped = convert_to_webp(src, tmp_path / "strip", metadata=STRIP)

    assert read_metadata(kept.output)[1] > 0
    assert read_metadata(stripped.output) == (0, 0)


def test_png_honours_the_metadata_choice(
    make_heic, exif_with_location, read_metadata, tmp_path
):
    src = make_heic("phone.heic", exif=exif_with_location)

    kept = convert_heic(src, tmp_path / "keep", fmt="png", metadata=KEEP)
    stripped = convert_heic(src, tmp_path / "strip", fmt="png", metadata=STRIP)

    assert read_metadata(kept.output)[1] > 0
    assert read_metadata(stripped.output) == (0, 0)


def test_compressing_honours_the_metadata_choice(
    make_heic, exif_with_location, read_metadata, tmp_path
):
    src = make_heic("phone.heic", width=600, height=400, exif=exif_with_location)
    as_jpg = convert_heic(src, tmp_path / "jpg", fmt="jpg", metadata=KEEP).output

    kept = compress(as_jpg, tmp_path / "keep", reduce_pct=30, metadata=KEEP)
    stripped = compress(as_jpg, tmp_path / "strip", reduce_pct=30, metadata=STRIP)

    assert read_metadata(kept.output)[1] > 0
    assert read_metadata(stripped.output) == (0, 0)


def test_the_orientation_tag_is_never_written_back(
    make_heic, exif_rotated_90, read_metadata, tmp_path
):
    """Rotation is baked into the pixels, so the tag would rotate them twice."""
    from PIL import Image

    src = make_heic("rotated.heic", width=640, height=480, exif=exif_rotated_90)

    result = convert_heic(src, tmp_path / "out", fmt="jpg", metadata=KEEP)

    with Image.open(result.output) as img:
        assert img.getexif().get(274, 1) == 1
        assert img.size == (480, 640)


def test_a_source_without_metadata_is_handled_calmly(make_jpg, read_metadata, tmp_path):
    src = make_jpg("plain.jpg")

    result = convert_to_webp(src, tmp_path / "out", metadata=KEEP)

    assert result.status == "ok"
    assert read_metadata(result.output) == (0, 0)


def test_an_unknown_metadata_mode_is_rejected(make_jpg, tmp_path):
    with pytest.raises(ValueError):
        convert_to_webp(make_jpg("photo.jpg"), tmp_path / "out", metadata="whatever")
