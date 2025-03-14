import pytest

from shared.banner import (
    BYLINE,
    MissingGlyph,
    banner_lines,
    big_width,
    glyph_table,
    gradient_colors,
    medium_width,
    subtitle_for,
)

TITLES = ["IMG TOOLKIT", "VID TOOLKIT"]
SUBTITLE = "download  ·  formats  ·  audio only"


@pytest.mark.parametrize("title", TITLES)
@pytest.mark.parametrize("width", [20, 30, 40, 78, 100, 200])
def test_every_line_fills_the_terminal_width_exactly(title, width):
    """The gradient runs the full width, so ragged lines would show as gaps."""
    lines = banner_lines(width, title)

    assert {len(line) for line in lines} == {width}


@pytest.mark.parametrize("title", TITLES)
def test_a_wide_terminal_gets_the_big_font(title):
    lines = banner_lines(big_width(title), title)

    assert len(lines) == 7, "six art rows plus the byline"
    assert "█" in lines[0]


@pytest.mark.parametrize("title", TITLES)
def test_a_medium_terminal_steps_down_to_the_compact_font(title):
    lines = banner_lines(big_width(title) - 1, title)

    assert len(lines) == 4, "three art rows plus the byline"
    assert "█" not in lines[0]
    assert "╦" in lines[0] or "╔" in lines[0]


@pytest.mark.parametrize("title", TITLES)
def test_a_narrow_terminal_falls_back_to_plain_text(title):
    lines = banner_lines(medium_width(title) - 1, title)

    assert len(lines) == 2
    assert title in lines[0]
    assert BYLINE in lines[1]


@pytest.mark.parametrize("title", TITLES)
def test_art_is_centred_in_the_terminal(title):
    first = banner_lines(120, title)[0]
    left = len(first) - len(first.lstrip())
    right = len(first) - len(first.rstrip())

    assert abs(left - right) <= 1


def test_byline_credits_rj():
    assert banner_lines(100, "IMG TOOLKIT")[-1].rstrip().endswith(BYLINE)


def test_byline_sits_under_the_right_edge_of_the_art():
    lines = banner_lines(100, "IMG TOOLKIT")
    art_right = max(len(line.rstrip()) for line in lines[:-1])

    assert len(lines[-1].rstrip()) == art_right


def test_every_glyph_is_rectangular_and_the_same_height():
    """Hand-drawn art drifts. A ragged glyph would skew everything after it."""
    for name, table in glyph_table().items():
        heights = {len(rows) for rows in table.values()}
        assert len(heights) == 1, f"{name}: glyphs disagree on height"
        for char, rows in table.items():
            assert len({len(r) for r in rows}) == 1, f"{name} {char!r}: ragged rows"


@pytest.mark.parametrize("title", TITLES)
def test_both_fonts_can_spell_every_toolkit_name(title):
    for name, table in glyph_table().items():
        missing = {c for c in title if c not in table}
        assert not missing, f"{name} cannot spell {title}: missing {missing}"


def test_a_title_the_font_cannot_spell_says_so():
    """Better a clear error than a KeyError from deep inside the renderer."""
    with pytest.raises(MissingGlyph):
        banner_lines(200, "ZZZ")


def test_subtitle_is_shown_when_it_fits():
    assert subtitle_for(100, SUBTITLE) == SUBTITLE
    assert subtitle_for(len(SUBTITLE), SUBTITLE) == SUBTITLE


def test_subtitle_is_dropped_rather_than_chopped_mid_word():
    assert subtitle_for(len(SUBTITLE) - 1, SUBTITLE) is None


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
