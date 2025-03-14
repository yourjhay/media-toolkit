from pathlib import Path

import pytest

from image_toolkit.discovery import HEIC_EXTS, RASTER_EXTS
from image_toolkit.planning import (
    OPERATIONS,
    default_output_dir,
    extensions_for,
    human_bytes,
    make_operation,
)


def test_default_output_dir_for_a_directory_is_a_subfolder(tmp_path):
    assert default_output_dir(tmp_path) == tmp_path / "converted"


def test_default_output_dir_for_a_single_file_sits_beside_it(make_jpg, tmp_path):
    src = make_jpg("photo.jpg")

    assert default_output_dir(src) == tmp_path / "converted"


@pytest.mark.parametrize(
    "size,expected",
    [(0, "0 B"), (512, "512 B"), (1536, "1.5 KB"), (5 * 1024 * 1024, "5.0 MB")],
)
def test_human_bytes_reads_naturally(size, expected):
    assert human_bytes(size) == expected


def test_human_bytes_keeps_the_sign_when_a_file_grew():
    assert human_bytes(-2048) == "-2.0 KB"


def test_heic_operation_looks_for_heic_files():
    assert extensions_for("heic") == HEIC_EXTS


def test_webp_and_compress_operations_look_for_jpg_and_png():
    assert extensions_for("webp") == RASTER_EXTS
    assert extensions_for("compress") == RASTER_EXTS


def test_every_advertised_operation_has_extensions():
    for key in OPERATIONS:
        assert extensions_for(key)


def test_made_operation_converts_a_real_file(make_heic, tmp_path):
    src = make_heic("shot.heic")
    op = make_operation("heic", tmp_path / "out", fmt="png")

    result = op(src)

    assert result.status == "ok"
    assert result.output.suffix == ".png"


def test_made_compress_operation_carries_its_reduction_target(make_jpg, tmp_path):
    src = make_jpg("photo.jpg", width=800, height=600, quality=95)
    op = make_operation("compress", tmp_path / "out", reduce_pct=60)

    result = op(src)

    assert result.output_bytes <= result.source_bytes * 0.4


def test_unknown_operation_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        make_operation("nonsense", tmp_path)


def test_quit_choice_has_a_real_value_not_none():
    """questionary substitutes the title when a Choice value is None.

    A None-valued quit entry therefore comes back as the string "Quit",
    silently failing any `is None` check and dropping the user into the
    next prompt instead of exiting.
    """
    from image_toolkit.planning import QUIT, operation_choices

    quit_entries = [c for c in operation_choices() if c.title == "Quit"]

    assert len(quit_entries) == 1
    assert quit_entries[0].value == QUIT
    assert quit_entries[0].value is not None


def test_quit_sentinel_cannot_collide_with_an_operation():
    from image_toolkit.planning import QUIT

    assert QUIT not in OPERATIONS


def test_menu_offers_every_operation_then_quit():
    from image_toolkit.planning import QUIT, operation_choices

    values = [c.value for c in operation_choices()]

    assert values == list(OPERATIONS) + [QUIT]


def test_tab_completion_trailing_space_is_stripped():
    """questionary's path completer appends a space after a completed name."""
    from image_toolkit.planning import clean_path_input

    assert clean_path_input("/Users/rj/Downloads/IMG_3319.HEIC ") == Path(
        "/Users/rj/Downloads/IMG_3319.HEIC"
    )


def test_surrounding_whitespace_is_stripped():
    from image_toolkit.planning import clean_path_input

    assert clean_path_input("   /tmp/photos\t") == Path("/tmp/photos")


@pytest.mark.parametrize("quoted", ["'/tmp/my photos'", '"/tmp/my photos"'])
def test_quoted_paths_are_unwrapped(quoted):
    from image_toolkit.planning import clean_path_input

    assert clean_path_input(quoted) == Path("/tmp/my photos")


def test_drag_and_drop_backslash_escapes_are_undone():
    """Dragging a file into a macOS terminal escapes spaces and parentheses."""
    from image_toolkit.planning import clean_path_input

    assert clean_path_input(r"/tmp/my\ photos\ \(2\)") == Path("/tmp/my photos (2)")


def test_a_quoted_path_keeps_its_literal_backslashes():
    from image_toolkit.planning import clean_path_input

    assert clean_path_input(r"'/tmp/odd\name'") == Path(r"/tmp/odd\name")


def test_tilde_is_expanded_to_the_home_directory():
    from image_toolkit.planning import clean_path_input

    assert clean_path_input("~/Downloads") == Path.home() / "Downloads"


def test_quoted_then_padded_then_completed_all_at_once():
    from image_toolkit.planning import clean_path_input

    assert clean_path_input('  "~/my photos"  ') == Path.home() / "my photos"


def test_empty_input_is_rejected_rather_than_meaning_the_current_directory():
    """Path("") is Path("."), which exists — it would silently accept the cwd."""
    from image_toolkit.planning import clean_path_input

    for blank in ("", "   ", "''", '""'):
        with pytest.raises(ValueError):
            clean_path_input(blank)


def test_a_saving_is_labelled_as_saved():
    from image_toolkit.planning import size_change_row

    assert size_change_row(1536) == ("Space saved", "1.5 KB")


def test_growth_is_labelled_as_growth_not_a_negative_saving():
    """HEIC out-compresses JPEG, so HEIC→JPG routinely produces a bigger file."""
    from image_toolkit.planning import size_change_row

    assert size_change_row(-1536) == ("Size increase", "1.5 KB")


def test_no_change_reads_as_a_saving_of_nothing():
    from image_toolkit.planning import size_change_row

    assert size_change_row(0) == ("Space saved", "0 B")


def test_estimate_reads_as_a_shrink_when_the_output_is_smaller():
    from image_toolkit.planning import format_estimate

    assert format_estimate(500, 1000) == "≈ 500 B  (from 1000 B, -50%)"


def test_estimate_reads_as_growth_when_the_output_is_bigger():
    from image_toolkit.planning import format_estimate

    assert format_estimate(1500, 1000) == "≈ 1.5 KB  (from 1000 B, +50%)"


def test_estimate_says_same_size_rather_than_zero_percent():
    from image_toolkit.planning import format_estimate

    assert format_estimate(1000, 1000) == "≈ 1000 B  (from 1000 B, same size)"


def test_estimate_omits_the_percentage_when_there_is_nothing_to_compare():
    from image_toolkit.planning import format_estimate

    assert format_estimate(500, 0) == "≈ 500 B"


def test_sample_file_is_the_median_by_size(make_jpg):
    """The median resists one enormous panorama skewing the whole estimate."""
    from image_toolkit.planning import median_by_size

    small = make_jpg("small.jpg", width=64, height=64)
    middle = make_jpg("middle.jpg", width=400, height=300)
    huge = make_jpg("huge.jpg", width=1200, height=900)

    assert median_by_size([huge, small, middle]) == middle


def test_sample_file_of_a_single_item_is_that_item(make_jpg):
    from image_toolkit.planning import median_by_size

    only = make_jpg("only.jpg")

    assert median_by_size([only]) == only


def test_sample_file_of_nothing_is_nothing():
    from image_toolkit.planning import median_by_size

    assert median_by_size([]) is None
