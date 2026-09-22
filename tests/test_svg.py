"""Reading an SVG's own idea of how big it is.

A vector has no pixels, so the size has to come from the file's width and
height, or failing that from its viewBox. Both are optional, both take units,
and either can be a percentage that means nothing on its own.
"""

import pytest

from image_toolkit.svg import intrinsic_size, render_size


def svg(attrs: str) -> bytes:
    return f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}><rect width="1" height="1"/></svg>'.encode()


def test_plain_width_and_height_are_read():
    assert intrinsic_size(svg('width="120" height="80"')) == (120.0, 80.0)


def test_pixel_units_are_read():
    assert intrinsic_size(svg('width="120px" height="80px"')) == (120.0, 80.0)


def test_decimal_sizes_survive():
    assert intrinsic_size(svg('width="120.5" height="80.25"')) == (120.5, 80.25)


def test_points_are_converted_to_pixels():
    """72pt is an inch, which is 96 CSS pixels."""
    width, height = intrinsic_size(svg('width="72pt" height="36pt"'))

    assert width == pytest.approx(96.0)
    assert height == pytest.approx(48.0)


def test_the_viewbox_is_used_when_there_is_no_width():
    assert intrinsic_size(svg('viewBox="0 0 200 100"')) == (200.0, 100.0)


def test_a_percentage_width_falls_back_to_the_viewbox():
    """width="100%" is meaningless without knowing what it is inside."""
    assert intrinsic_size(svg('width="100%" height="100%" viewBox="0 0 64 64"')) == (64.0, 64.0)


def test_a_percentage_with_no_viewbox_gives_nothing():
    assert intrinsic_size(svg('width="100%" height="100%"')) is None


def test_a_file_with_neither_gives_nothing():
    assert intrinsic_size(svg('')) is None


def test_something_that_is_not_svg_gives_nothing():
    assert intrinsic_size(b"this is not xml at all") is None


def test_a_truncated_file_gives_nothing():
    assert intrinsic_size(b'<svg xmlns="http://www.w3.org/2000/svg" width="10"') is None


# --- working out the output size -------------------------------------------

def test_a_scale_multiplies_both_sides():
    assert render_size((120, 80), scale=2.0) == (240, 160)


def test_a_fractional_scale_rounds_to_whole_pixels():
    assert render_size((121, 81), scale=1.5) == (182, 122)


def test_an_exact_width_keeps_the_proportions():
    assert render_size((120, 80), width=600) == (600, 400)


def test_an_exact_width_wins_over_a_scale():
    assert render_size((120, 80), scale=2.0, width=600) == (600, 400)


def test_a_size_is_never_less_than_one_pixel():
    assert render_size((120, 80), scale=0.001) == (1, 1)


def test_a_drawing_with_no_size_at_all_is_rendered_square():
    """No width, height or viewBox means no aspect ratio exists to preserve.

    The renderer refuses a width on its own in that case, so a square is the
    assumption — declared out loud in the result rather than made quietly."""
    assert render_size(None, width=600) == (600, 600)


def test_without_an_intrinsic_size_a_scale_has_nothing_to_multiply():
    assert render_size(None, scale=2.0) == (None, None)
