import pytest
from PIL import Image

from image_toolkit.core import KEEP, STRIP, resize


def test_a_width_limit_produces_the_expected_dimensions(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=4000, height=3000)

    result = resize(src, tmp_path / "out", max_width=1000)

    assert result.status == "ok"
    with Image.open(result.output) as img:
        assert img.size == (1000, 750)
        assert img.format == "JPEG"


def test_the_output_keeps_the_source_name_and_format(make_png, tmp_path):
    src = make_png("chart.png", width=800, height=600)

    result = resize(src, tmp_path / "out", percent=50)

    assert result.output.name == "chart.png"
    with Image.open(result.output) as img:
        assert img.size == (400, 300)
        assert img.format == "PNG"


def test_transparency_survives_a_resize(make_png, tmp_path):
    src = make_png("badge.png", width=256, height=256, mode="RGBA")

    result = resize(src, tmp_path / "out", max_width=64)

    with Image.open(result.output) as img:
        alpha = img.convert("RGBA").getchannel("A").tobytes()
        assert min(alpha) < 250


def test_an_image_already_inside_the_box_is_left_at_its_size(make_jpg, tmp_path):
    src = make_jpg("small.jpg", width=400, height=300)

    result = resize(src, tmp_path / "out", max_width=2000)

    with Image.open(result.output) as img:
        assert img.size == (400, 300)
    assert "already" in result.detail.lower()


def test_the_result_records_the_dimension_change(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=4000, height=3000)

    result = resize(src, tmp_path / "out", max_width=1000)

    assert "4000" in result.detail and "1000" in result.detail


def test_resizing_shrinks_the_file(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=2000, height=1500, quality=95)

    result = resize(src, tmp_path / "out", max_width=500)

    assert result.output_bytes < result.source_bytes


def test_metadata_choice_is_honoured(make_heic, exif_with_location, read_metadata, tmp_path):
    from image_toolkit.core import convert_heic

    heic = make_heic("phone.heic", width=800, height=600, exif=exif_with_location)
    src = convert_heic(heic, tmp_path / "jpg", fmt="jpg", metadata=KEEP).output

    kept = resize(src, tmp_path / "keep", max_width=400, metadata=KEEP)
    stripped = resize(src, tmp_path / "strip", max_width=400, metadata=STRIP)

    assert read_metadata(kept.output)[1] > 0
    assert read_metadata(stripped.output) == (0, 0)


def test_existing_output_is_left_alone_by_default(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "photo.jpg").write_bytes(b"keep me")

    result = resize(src, out_dir, max_width=100)

    assert result.status == "skipped"
    assert (out_dir / "photo.jpg").read_bytes() == b"keep me"


def test_it_refuses_to_write_over_the_source(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    original = src.read_bytes()

    result = resize(src, src.parent, max_width=100)

    assert result.status == "failed"
    assert src.read_bytes() == original


def test_an_unreadable_input_is_reported_not_raised(touch, tmp_path):
    result = resize(touch("broken.jpg", b"not a jpeg"), tmp_path / "out", max_width=100)

    assert result.status == "failed"
    assert result.detail


def test_contradictory_instructions_are_rejected_up_front(make_jpg, tmp_path):
    """A caller's mistake, not one file's problem, so it raises."""
    with pytest.raises(ValueError):
        resize(make_jpg("photo.jpg"), tmp_path / "out", percent=50, max_width=100)


def test_asking_for_no_resize_at_all_is_rejected(make_jpg, tmp_path):
    with pytest.raises(ValueError):
        resize(make_jpg("photo.jpg"), tmp_path / "out")
