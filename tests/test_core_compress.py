import pytest
from PIL import Image

from image_toolkit.core import compress


def test_jpg_hits_the_requested_size_reduction(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=800, height=600, quality=95)

    result = compress(src, tmp_path / "out", reduce_pct=50)

    assert result.status == "ok"
    assert result.output_bytes <= result.source_bytes * 0.5


def test_compressed_jpg_is_still_a_valid_jpeg_of_the_same_size(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=800, height=600, quality=95)

    result = compress(src, tmp_path / "out", reduce_pct=40)

    with Image.open(result.output) as img:
        assert img.format == "JPEG"
        assert img.size == (800, 600)


def test_output_keeps_the_source_extension(make_png, tmp_path):
    src = make_png("chart.png", width=400, height=300)

    result = compress(src, tmp_path / "out", reduce_pct=30)

    assert result.output.name == "chart.png"
    with Image.open(result.output) as img:
        assert img.format == "PNG"


def test_png_with_transparency_stays_transparent(make_png, tmp_path):
    src = make_png("badge.png", width=256, height=256, mode="RGBA")

    result = compress(src, tmp_path / "out", reduce_pct=30)

    with Image.open(result.output) as img:
        alpha = img.convert("RGBA").getchannel("A").tobytes()
        assert min(alpha) < 250, "alpha channel was flattened to opaque"
        assert img.size == (256, 256)


def test_result_reports_the_reduction_actually_achieved(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=800, height=600, quality=95)

    result = compress(src, tmp_path / "out", reduce_pct=50)

    expected = (1 - result.output_bytes / result.source_bytes) * 100
    assert result.achieved_pct == pytest.approx(expected, abs=0.01)
    assert result.achieved_pct >= 50


def test_unreachable_target_is_reported_as_short_not_silently_accepted(make_jpg, tmp_path):
    """An already-squeezed thumbnail cannot lose 95% more. Say so."""
    src = make_jpg("tiny.jpg", width=64, height=64, quality=15)

    result = compress(src, tmp_path / "out", reduce_pct=95)

    assert result.status == "short"
    assert result.achieved_pct < 95
    assert "95" in result.detail


def test_output_is_never_larger_than_the_source(make_jpg, tmp_path):
    src = make_jpg("tiny.jpg", width=64, height=64, quality=15)

    result = compress(src, tmp_path / "out", reduce_pct=95)

    assert result.output_bytes <= result.source_bytes


def test_refuses_to_write_over_the_source_file(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    original = src.read_bytes()

    result = compress(src, src.parent, reduce_pct=50)

    assert result.status == "failed"
    assert src.read_bytes() == original


def test_reduction_outside_the_valid_range_is_rejected(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")

    with pytest.raises(ValueError):
        compress(src, tmp_path / "out", reduce_pct=0)

    with pytest.raises(ValueError):
        compress(src, tmp_path / "out", reduce_pct=100)


def test_existing_output_is_left_alone_by_default(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "photo.jpg").write_bytes(b"keep me")

    result = compress(src, out_dir, reduce_pct=50)

    assert result.status == "skipped"
    assert (out_dir / "photo.jpg").read_bytes() == b"keep me"


def test_unreadable_input_is_reported_not_raised(touch, tmp_path):
    broken = touch("broken.png", b"not a png at all")

    result = compress(broken, tmp_path / "out", reduce_pct=50)

    assert result.status == "failed"
    assert result.detail
