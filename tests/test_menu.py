import pytest

from image_toolkit.menu import (
    CARD_GAP,
    MIN_CARD_WIDTH,
    MenuItem,
    card_width_for,
    columns_for,
    next_index,
    plain,
    render_grid,
)

ITEMS = [
    MenuItem("heic", "HEIC / HEIF", "→ JPG or PNG", "#00d6aa"),
    MenuItem("webp", "JPG / PNG", "→ WebP", "#4aa8ff"),
    MenuItem("compress", "Compress", "JPG / PNG to a target size", "#f0a02a"),
    MenuItem("quit", "Quit", "", "#8b949e"),
]


def test_a_wide_terminal_gets_two_columns():
    assert columns_for(100) == 2


def test_a_narrow_terminal_drops_to_one_column():
    assert columns_for(MIN_CARD_WIDTH * 2 + CARD_GAP - 1) == 1


def test_it_never_uses_more_than_two_columns():
    assert columns_for(400) == 2


def test_cards_never_grow_past_a_readable_width():
    assert card_width_for(400, columns=2) <= 44


def test_cards_never_shrink_below_the_minimum():
    assert card_width_for(10, columns=1) >= MIN_CARD_WIDTH


@pytest.mark.parametrize("width", [60, 80, 100, 160])
def test_every_rendered_line_is_the_same_length(width):
    lines = render_grid(ITEMS, selected=0, width=width)

    assert len({len(plain(line)) for line in lines}) == 1


def test_four_items_lay_out_two_per_row():
    lines = [plain(line) for line in render_grid(ITEMS, selected=0, width=100)]
    text = "\n".join(lines)

    first_row = [line for line in lines if "HEIC / HEIF" in line]
    assert first_row, "first card should be present"
    assert "JPG / PNG" in first_row[0], "second card should share the row"
    assert "Compress" not in first_row[0], "third card belongs on the next row"
    assert "Compress" in text and "Quit" in text


def test_one_column_stacks_every_card():
    """Distinct words here, so a title cannot match inside another's detail."""
    items = [
        MenuItem("a", "Alpha", "first", "#111111"),
        MenuItem("b", "Bravo", "second", "#222222"),
        MenuItem("c", "Charlie", "third", "#333333"),
    ]

    lines = [plain(line) for line in render_grid(items, selected=0, width=30)]

    for item in items:
        rows = [line for line in lines if item.title in line]
        assert len(rows) == 1
        assert sum(other.title in rows[0] for other in items) == 1


def test_each_card_is_numbered_for_direct_selection():
    text = "\n".join(plain(line) for line in render_grid(ITEMS, selected=0, width=100))

    for number in range(1, len(ITEMS) + 1):
        assert f" {number} " in text


def test_the_selected_card_is_drawn_with_a_heavy_border():
    """Readable even where colour is unavailable."""
    first = "\n".join(plain(line) for line in render_grid(ITEMS, selected=0, width=100))
    second = "\n".join(plain(line) for line in render_grid(ITEMS, selected=1, width=100))

    assert first.count("┏") == 1
    assert second.count("┏") == 1
    assert first != second


def test_the_selected_card_is_styled_in_its_own_colour():
    fragments = [f for line in render_grid(ITEMS, selected=1, width=100) for f in line]
    styles = " ".join(style for style, _ in fragments)

    assert ITEMS[1].color in styles


def test_a_long_detail_is_truncated_rather_than_breaking_the_grid():
    long_item = MenuItem("x", "Title", "detail " * 40, "#ffffff")

    lines = render_grid([long_item], selected=0, width=60)

    assert len({len(plain(line)) for line in lines}) == 1


def test_moving_right_advances_by_one():
    assert next_index(0, "right", count=4, columns=2) == 1


def test_moving_down_advances_by_a_whole_row():
    assert next_index(0, "down", count=4, columns=2) == 2


def test_moving_up_from_the_second_row_returns_to_the_first():
    assert next_index(3, "up", count=4, columns=2) == 1


def test_movement_stops_at_the_edges_rather_than_wrapping():
    assert next_index(0, "left", count=4, columns=2) == 0
    assert next_index(3, "right", count=4, columns=2) == 3
    assert next_index(0, "up", count=4, columns=2) == 0
    assert next_index(3, "down", count=4, columns=2) == 3


def test_moving_down_onto_a_missing_card_stops_at_the_last_one():
    """Five items in two columns leaves a gap under the last card."""
    assert next_index(4, "down", count=5, columns=2) == 4
    assert next_index(3, "down", count=5, columns=2) == 4


def test_an_unknown_direction_changes_nothing():
    assert next_index(2, "sideways", count=4, columns=2) == 2
