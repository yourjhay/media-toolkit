from PIL import Image

from image_toolkit.core import convert_heic


def test_heic_to_jpg_writes_a_real_jpeg(make_heic, tmp_path):
    src = make_heic("shot.heic", width=640, height=480)
    out_dir = tmp_path / "out"

    result = convert_heic(src, out_dir, fmt="jpg")

    assert result.status == "ok"
    assert result.output == out_dir / "shot.jpg"
    with Image.open(result.output) as img:
        assert img.format == "JPEG"
        assert img.size == (640, 480)


def test_heic_to_png_writes_a_real_png(make_heic, tmp_path):
    src = make_heic("shot.heic", width=320, height=240)

    result = convert_heic(src, tmp_path / "out", fmt="png")

    with Image.open(result.output) as img:
        assert img.format == "PNG"
        assert img.size == (320, 240)


def test_creates_output_directory_when_absent(make_heic, tmp_path):
    src = make_heic("shot.heic")
    out_dir = tmp_path / "deeply" / "nested" / "out"

    result = convert_heic(src, out_dir, fmt="jpg")

    assert result.output.exists()


def test_exif_rotation_is_baked_into_the_pixels(make_heic, exif_rotated_90, tmp_path):
    """iPhone HEIC stores rotation in EXIF; a viewer-agnostic JPEG must not."""
    src = make_heic("rotated.heic", width=640, height=480, exif=exif_rotated_90)

    result = convert_heic(src, tmp_path / "out", fmt="jpg")

    with Image.open(result.output) as img:
        assert img.size == (480, 640), "portrait orientation should be applied"
        assert img.getexif().get(274, 1) == 1, "orientation tag should be neutralised"


def test_existing_output_is_left_alone_by_default(make_heic, tmp_path):
    src = make_heic("shot.heic")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    existing = out_dir / "shot.jpg"
    existing.write_bytes(b"do not clobber me")

    result = convert_heic(src, out_dir, fmt="jpg")

    assert result.status == "skipped"
    assert existing.read_bytes() == b"do not clobber me"


def test_overwrite_replaces_existing_output(make_heic, tmp_path):
    src = make_heic("shot.heic")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "shot.jpg").write_bytes(b"stale")

    result = convert_heic(src, out_dir, fmt="jpg", overwrite=True)

    assert result.status == "ok"
    with Image.open(result.output) as img:
        assert img.format == "JPEG"


def test_unreadable_input_is_reported_not_raised(touch, tmp_path):
    broken = touch("broken.heic", b"this is not a heic file")

    result = convert_heic(broken, tmp_path / "out", fmt="jpg")

    assert result.status == "failed"
    assert result.detail


def test_result_records_byte_sizes(make_heic, tmp_path):
    src = make_heic("shot.heic")

    result = convert_heic(src, tmp_path / "out", fmt="jpg")

    assert result.source_bytes == src.stat().st_size
    assert result.output_bytes == result.output.stat().st_size
