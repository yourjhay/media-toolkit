from pathlib import Path

from PIL import Image

from image_toolkit.core import compress, convert_heic, convert_to_webp
from image_toolkit.planning import assign_output_paths, make_operation, output_name


def test_heic_honours_an_explicit_output_path(make_heic, tmp_path):
    src = make_heic("shot.heic")
    chosen = tmp_path / "out" / "renamed-2.jpg"

    result = convert_heic(src, tmp_path / "out", fmt="jpg", out_path=chosen)

    assert result.output == chosen
    with Image.open(chosen) as img:
        assert img.format == "JPEG"


def test_webp_honours_an_explicit_output_path(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    chosen = tmp_path / "out" / "photo-3.webp"

    result = convert_to_webp(src, tmp_path / "out", out_path=chosen)

    assert result.output == chosen
    assert chosen.exists()


def test_compress_honours_an_explicit_output_path(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=800, height=600, quality=95)
    chosen = tmp_path / "out" / "photo-2.jpg"

    result = compress(src, tmp_path / "out", reduce_pct=50, out_path=chosen)

    assert result.output == chosen
    assert chosen.stat().st_size <= result.source_bytes * 0.5


def test_an_explicit_path_still_refuses_to_overwrite_the_source(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    original = src.read_bytes()

    result = compress(src, tmp_path, reduce_pct=50, out_path=src)

    assert result.status == "failed"
    assert src.read_bytes() == original


def test_an_explicit_path_still_skips_an_existing_file(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")
    chosen = tmp_path / "out" / "taken.webp"
    chosen.parent.mkdir()
    chosen.write_bytes(b"keep me")

    result = convert_to_webp(src, tmp_path / "out", out_path=chosen)

    assert result.status == "skipped"
    assert chosen.read_bytes() == b"keep me"


def test_a_batch_with_colliding_names_writes_both_files(make_jpg, tmp_path):
    """The whole point: neither source is lost to the other."""
    a = make_jpg("a/photo.jpg", width=200, height=200)
    b = make_jpg("b/photo.jpg", width=400, height=400)
    dest = tmp_path / "out"

    outputs = assign_output_paths([a, b], dest, lambda p: output_name("webp", p))
    op = make_operation("webp", dest, outputs=outputs)
    results = [op(a), op(b)]

    assert [r.status for r in results] == ["ok", "ok"]
    assert sorted(p.name for p in dest.iterdir()) == ["photo-2.webp", "photo.webp"]
    with Image.open(dest / "photo.webp") as img:
        assert img.size == (200, 200)
    with Image.open(dest / "photo-2.webp") as img:
        assert img.size == (400, 400)


def test_an_operation_without_an_output_map_behaves_as_before(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")

    result = make_operation("webp", tmp_path / "out")(src)

    assert result.output == tmp_path / "out" / "photo.webp"
