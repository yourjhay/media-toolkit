from pathlib import Path

from image_toolkit.planning import assign_output_paths, output_name


def _webp(src: Path) -> str:
    return f"{src.stem}.webp"


def test_names_are_left_alone_when_nothing_collides(tmp_path):
    files = [Path("a/one.jpg"), Path("b/two.jpg")]

    assigned = assign_output_paths(files, tmp_path, _webp)

    assert assigned[files[0]] == tmp_path / "one.webp"
    assert assigned[files[1]] == tmp_path / "two.webp"


def test_a_second_file_of_the_same_name_is_numbered(tmp_path):
    """Recursive runs flatten subfolders, so two photo.jpg files can meet."""
    a, b = Path("a/photo.jpg"), Path("b/photo.jpg")

    assigned = assign_output_paths([a, b], tmp_path, _webp)

    assert assigned[a] == tmp_path / "photo.webp"
    assert assigned[b] == tmp_path / "photo-2.webp"


def test_numbering_keeps_counting_for_further_collisions(tmp_path):
    files = [Path(f"{d}/photo.jpg") for d in "abcd"]

    assigned = assign_output_paths(files, tmp_path, _webp)

    assert [assigned[f].name for f in files] == [
        "photo.webp",
        "photo-2.webp",
        "photo-3.webp",
        "photo-4.webp",
    ]


def test_a_source_already_named_like_a_disambiguation_is_not_clobbered(tmp_path):
    """photo-2.jpg claims photo-2.webp first, so the collision skips past it."""
    first = Path("a/photo.jpg")
    literal = Path("a/photo-2.jpg")
    collides = Path("b/photo.jpg")

    assigned = assign_output_paths([first, literal, collides], tmp_path, _webp)

    assert assigned[first].name == "photo.webp"
    assert assigned[literal].name == "photo-2.webp"
    assert assigned[collides].name == "photo-3.webp"


def test_collisions_are_detected_case_insensitively(tmp_path):
    """macOS filesystems are case-insensitive: Photo.webp and photo.webp are one file."""
    upper, lower = Path("a/Photo.jpg"), Path("b/photo.jpg")

    assigned = assign_output_paths([upper, lower], tmp_path, _webp)

    assert assigned[upper].name != assigned[lower].name
    assert assigned[lower].name == "photo-2.webp"


def test_every_input_gets_an_entry(tmp_path):
    files = [Path(f"{i}.jpg") for i in range(5)]

    assert set(assign_output_paths(files, tmp_path, _webp)) == set(files)


def test_no_two_sources_are_ever_assigned_the_same_output(tmp_path):
    files = [Path("a/x.jpg"), Path("b/x.jpg"), Path("c/x.jpg"), Path("d/x-2.jpg")]

    assigned = assign_output_paths(files, tmp_path, _webp)

    assert len({p.name.casefold() for p in assigned.values()}) == len(files)


def test_nothing_in_means_nothing_out(tmp_path):
    assert assign_output_paths([], tmp_path, _webp) == {}


def test_heic_output_name_takes_the_chosen_format():
    assert output_name("heic", Path("IMG_1.HEIC"), fmt="jpg") == "IMG_1.jpg"
    assert output_name("heic", Path("IMG_1.HEIC"), fmt="png") == "IMG_1.png"


def test_webp_output_name_is_always_webp():
    assert output_name("webp", Path("photo.JPG")) == "photo.webp"


def test_compress_keeps_the_source_filename_exactly():
    """Same format in, same out — including the original extension's case."""
    assert output_name("compress", Path("Chart.PNG")) == "Chart.PNG"
