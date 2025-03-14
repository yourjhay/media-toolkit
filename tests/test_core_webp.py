from PIL import Image

from image_toolkit.core import convert_to_webp


def test_jpg_becomes_a_real_webp(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=640, height=480)

    result = convert_to_webp(src, tmp_path / "out")

    assert result.status == "ok"
    assert result.output == tmp_path / "out" / "photo.webp"
    with Image.open(result.output) as img:
        assert img.format == "WEBP"
        assert img.size == (640, 480)


def test_png_transparency_survives_the_conversion(make_png, tmp_path):
    src = make_png("badge.png", width=64, height=64, mode="RGBA")

    result = convert_to_webp(src, tmp_path / "out")

    with Image.open(result.output) as img:
        assert img.mode == "RGBA"


def test_lossless_mode_reproduces_the_source_pixels(make_png, tmp_path):
    src = make_png("exact.png", width=64, height=64)

    result = convert_to_webp(src, tmp_path / "out", lossless=True)

    with Image.open(src) as original, Image.open(result.output) as converted:
        assert converted.convert("RGB").tobytes() == original.convert("RGB").tobytes()


def test_lower_quality_produces_a_smaller_file(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")

    high = convert_to_webp(src, tmp_path / "high", quality=95)
    low = convert_to_webp(src, tmp_path / "low", quality=20)

    assert low.output_bytes < high.output_bytes


def test_existing_output_is_left_alone_by_default(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "photo.webp").write_bytes(b"keep me")

    result = convert_to_webp(src, out_dir)

    assert result.status == "skipped"
    assert (out_dir / "photo.webp").read_bytes() == b"keep me"


def test_unreadable_input_is_reported_not_raised(touch, tmp_path):
    broken = touch("broken.jpg", b"definitely not a jpeg")

    result = convert_to_webp(broken, tmp_path / "out")

    assert result.status == "failed"
    assert result.detail
