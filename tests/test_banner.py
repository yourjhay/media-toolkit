import pytest

from image_toolkit.banner import (
    BIG_WIDTH,
    BYLINE,
    MEDIUM_WIDTH,
    PLAIN_TITLE,
    banner_lines,
    glyph_table,
    gradient_colors,
)


@pytest.mark.parametrize("width", [20, 28, 40, 81, 100, 200])
def test_every_line_fills_the_terminal_width_exactly(width):
    """The gradient runs the full width, so ragged lines would show as gaps."""
    lines = banner_lines(width)

    assert {len(line) for line in lines} == {width}


def test_a_wide_terminal_gets_the_big_font():
    lines = banner_lines(BIG_WIDTH)

    assert len(lines) == 7, "six art rows plus the byline"
    assert "█" in lines[0]


def test_a_medium_terminal_steps_down_to_the_compact_font():
    lines = banner_lines(BIG_WIDTH - 1)

    assert len(lines) == 4, "three art rows plus the byline"
    assert "█" not in lines[0]
    assert "╦" in lines[0]


def test_a_narrow_terminal_falls_back_to_plain_text():
    lines = banner_lines(MEDIUM_WIDTH - 1)

    assert len(lines) == 2
    assert PLAIN_TITLE in lines[0]
    assert BYLINE in lines[1]


@pytest.mark.parametrize("width", [MEDIUM_WIDTH, 100, 200])
def test_art_is_centred_in_the_terminal(width):
    first = banner_lines(width)[0]
    left = len(first) - len(first.lstrip())
    right = len(first) - len(first.rstrip())

    assert abs(left - right) <= 1


def test_byline_is_the_last_line_and_credits_rj():
    assert banner_lines(100)[-1].rstrip().endswith(BYLINE)


def test_byline_sits_under_the_right_edge_of_the_art(width=100):
    lines = banner_lines(width)
    art_right = max(len(line.rstrip()) for line in lines[:-1])

    assert len(lines[-1].rstrip()) == art_right


def test_every_glyph_is_rectangular_and_the_same_height():
    """Hand-drawn art drifts. A ragged glyph would skew everything after it."""
    for name, table in glyph_table().items():
        heights = {len(rows) for rows in table.values()}
        assert len(heights) == 1, f"{name}: glyphs disagree on height"
        for char, rows in table.items():
            assert len({len(r) for r in rows}) == 1, f"{name} {char!r}: ragged rows"


def test_both_fonts_cover_every_letter_of_the_title():
    for name, table in glyph_table().items():
        missing = {c for c in PLAIN_TITLE if c not in table}
        assert not missing, f"{name} is missing {missing}"


def test_gradient_spans_from_the_first_colour_to_the_last():
    colors = gradient_colors(5, (0, 0, 0), (100, 200, 250))

    assert len(colors) == 5
    assert colors[0] == (0, 0, 0)
    assert colors[-1] == (100, 200, 250)


def test_gradient_moves_monotonically():
    reds = [c[0] for c in gradient_colors(10, (0, 0, 0), (255, 255, 255))]

    assert reds == sorted(reds)


def test_single_step_gradient_is_the_start_colour():
    assert gradient_colors(1, (10, 20, 30), (200, 200, 200)) == [(10, 20, 30)]


def test_empty_gradient_is_empty():
    assert gradient_colors(0, (0, 0, 0), (255, 255, 255)) == []


def test_negative_length_gradient_is_rejected():
    with pytest.raises(ValueError):
        gradient_colors(-1, (0, 0, 0), (255, 255, 255))


def test_subtitle_is_shown_when_it_fits():
    from image_toolkit.banner import SUBTITLE, subtitle_for

    assert subtitle_for(100) == SUBTITLE
    assert subtitle_for(len(SUBTITLE)) == SUBTITLE


def test_subtitle_is_dropped_rather_than_chopped_mid_word():
    from image_toolkit.banner import SUBTITLE, subtitle_for

    assert subtitle_for(len(SUBTITLE) - 1) is None
    assert subtitle_for(24) is None
