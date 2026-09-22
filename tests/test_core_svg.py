import pytest
from PIL import Image

from image_toolkit.core import convert_svg

DRAWING = b'''<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80">
  <circle cx="40" cy="40" r="22" fill="#4aa8ff"/>
</svg>'''


@pytest.fixture
def drawing(tmp_path):
    path = tmp_path / "logo.svg"
    path.write_bytes(DRAWING)
    return path


def test_it_renders_at_twice_the_size_by_default(drawing, tmp_path):
    """A logo at its nominal size looks soft on any modern display."""
    result = convert_svg(drawing, tmp_path / "out")

    assert result.status == "ok"
    with Image.open(result.output) as img:
        assert img.size == (240, 160)
        assert img.format == "PNG"


def test_the_output_is_named_after_the_drawing(drawing, tmp_path):
    assert convert_svg(drawing, tmp_path / "out").output.name == "logo.png"


def test_a_scale_is_honoured(drawing, tmp_path):
    result = convert_svg(drawing, tmp_path / "out", scale=3.0)

    with Image.open(result.output) as img:
        assert img.size == (360, 240)


def test_an_exact_width_keeps_the_proportions(drawing, tmp_path):
    result = convert_svg(drawing, tmp_path / "out", width=600)

    with Image.open(result.output) as img:
        assert img.size == (600, 400)


def test_the_background_stays_transparent_by_default(drawing, tmp_path):
    result = convert_svg(drawing, tmp_path / "out")

    with Image.open(result.output) as img:
        alpha = img.convert("RGBA").getchannel("A").tobytes()
        assert min(alpha) == 0, "the corners should be see-through"


def test_a_background_colour_fills_it_in(drawing, tmp_path):
    result = convert_svg(drawing, tmp_path / "out", background="#ffffff")

    with Image.open(result.output) as img:
        rgba = img.convert("RGBA")
        assert min(rgba.getchannel("A").tobytes()) == 255
        assert rgba.getpixel((2, 2))[:3] == (255, 255, 255)


def test_the_result_says_what_size_it_made(drawing, tmp_path):
    result = convert_svg(drawing, tmp_path / "out", scale=2.0)

    assert "240" in result.detail and "160" in result.detail


def test_existing_output_is_left_alone_by_default(drawing, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "logo.png").write_bytes(b"keep me")

    result = convert_svg(drawing, out_dir)

    assert result.status == "skipped"
    assert (out_dir / "logo.png").read_bytes() == b"keep me"


def test_overwrite_replaces_it(drawing, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "logo.png").write_bytes(b"stale")

    result = convert_svg(drawing, out_dir, overwrite=True)

    assert result.status == "ok"
    with Image.open(result.output) as img:
        assert img.format == "PNG"


def test_a_file_that_is_not_svg_is_reported_not_raised(tmp_path):
    broken = tmp_path / "broken.svg"
    broken.write_bytes(b"this is not an svg")

    result = convert_svg(broken, tmp_path / "out")

    assert result.status == "failed"
    assert result.detail


def test_a_drawing_with_no_size_of_its_own_still_renders(tmp_path):
    """No width, no height, no viewBox — the renderer picks something."""
    path = tmp_path / "sizeless.svg"
    path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')

    result = convert_svg(path, tmp_path / "out", width=300)

    assert result.status == "ok"
    with Image.open(result.output) as img:
        assert img.size[0] == 300
