import pytest

from image_toolkit.discovery import HEIC_EXTS, RASTER_EXTS, find_images


def test_finds_matching_images_and_ignores_other_files(make_jpg, make_png, touch, tmp_path):
    make_jpg("a.jpg")
    make_png("b.png")
    touch("notes.txt")

    found = find_images(tmp_path, RASTER_EXTS)

    assert [p.name for p in found] == ["a.jpg", "b.png"]


def test_non_recursive_ignores_subdirectories(make_jpg, tmp_path):
    make_jpg("top.jpg")
    make_jpg("nested/deep.jpg")

    found = find_images(tmp_path, RASTER_EXTS, recursive=False)

    assert [p.name for p in found] == ["top.jpg"]


def test_recursive_includes_subdirectories(make_jpg, tmp_path):
    make_jpg("top.jpg")
    make_jpg("nested/deep.jpg")

    found = find_images(tmp_path, RASTER_EXTS, recursive=True)

    assert [p.name for p in found] == ["deep.jpg", "top.jpg"]


def test_extension_match_is_case_insensitive(make_jpg, tmp_path):
    make_jpg("SHOUTY.JPG")

    found = find_images(tmp_path, RASTER_EXTS)

    assert [p.name for p in found] == ["SHOUTY.JPG"]


def test_single_file_path_returns_that_file(make_png, tmp_path):
    target = make_png("only.png")

    found = find_images(target, RASTER_EXTS)

    assert found == [target]


def test_single_file_of_wrong_type_returns_nothing(touch, tmp_path):
    target = touch("notes.txt")

    found = find_images(target, RASTER_EXTS)

    assert found == []


def test_excluded_directory_is_skipped(make_jpg, tmp_path):
    """Guards re-processing: the output dir often lives inside the source dir."""
    make_jpg("source.jpg")
    make_jpg("converted/already-done.jpg")

    found = find_images(tmp_path, RASTER_EXTS, recursive=True, exclude=[tmp_path / "converted"])

    assert [p.name for p in found] == ["source.jpg"]


def test_missing_path_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_images(tmp_path / "nope", RASTER_EXTS)


def test_heic_extensions_cover_both_spellings():
    assert HEIC_EXTS == {".heic", ".heif"}
