from image_toolkit.discovery import HEIC_EXTS, RASTER_EXTS
from image_toolkit.info import FileInfo, FolderInfo, inspect_source


def test_a_single_image_reports_its_name_size_and_location(make_jpg, tmp_path):
    src = make_jpg("holiday.jpg", width=640, height=480)

    info = inspect_source(src, RASTER_EXTS)

    assert isinstance(info, FileInfo)
    assert info.name == "holiday.jpg"
    assert info.size_bytes == src.stat().st_size
    assert info.location == tmp_path


def test_a_single_image_reports_its_dimensions_and_format(make_jpg):
    info = inspect_source(make_jpg("holiday.jpg", width=640, height=480), RASTER_EXTS)

    assert info.dimensions == (640, 480)
    assert info.format == "JPEG"
    assert info.error is None


def test_a_heic_reports_its_upright_dimensions(make_heic, exif_rotated_90):
    """Stored 640x480 with a rotate flag, so it is really a 480x640 portrait."""
    src = make_heic("rotated.heic", width=640, height=480, exif=exif_rotated_90)

    info = inspect_source(src, HEIC_EXTS)

    assert info.dimensions == (480, 640)


def test_an_unreadable_file_reports_the_problem_instead_of_raising(touch):
    info = inspect_source(touch("broken.jpg", b"not an image"), RASTER_EXTS)

    assert info.dimensions is None
    assert info.error


def test_a_folder_counts_the_matching_images_at_its_top_level(make_jpg, touch, tmp_path):
    make_jpg("a.jpg")
    make_jpg("b.jpg")
    touch("notes.txt")

    info = inspect_source(tmp_path, RASTER_EXTS)

    assert isinstance(info, FolderInfo)
    assert info.here_count == 2
    assert info.here_bytes == sum(p.stat().st_size for p in tmp_path.glob("*.jpg"))


def test_a_folder_counts_nested_images_separately(make_jpg, tmp_path):
    """Shown before the recursive prompt, so it can inform the answer."""
    make_jpg("top.jpg")
    make_jpg("sub/one.jpg")
    make_jpg("sub/deeper/two.jpg")

    info = inspect_source(tmp_path, RASTER_EXTS)

    assert info.here_count == 1
    assert info.nested_count == 2
    assert info.total_count == 3


def test_a_folder_with_nothing_matching_reports_zeroes(touch, tmp_path):
    touch("notes.txt")

    info = inspect_source(tmp_path, RASTER_EXTS)

    assert info.total_count == 0
    assert info.total_bytes == 0


def test_folder_reports_its_own_name_and_parent(make_jpg, tmp_path):
    make_jpg("photos/a.jpg")

    info = inspect_source(tmp_path / "photos", RASTER_EXTS)

    assert info.name == "photos"
    assert info.location == tmp_path


# --- vectors are not openable by an image library ---------------------------

SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="1" height="1"/></svg>'''


def test_an_svg_reports_its_size_rather_than_an_error(tmp_path):
    """Pillow cannot open a vector; that is not a problem with the file."""
    from image_toolkit.discovery import SVG_EXTS

    path = tmp_path / "logo.svg"
    path.write_bytes(SVG)

    info = inspect_source(path, SVG_EXTS)

    assert info.error is None, info.error
    assert info.dimensions == (120, 80)
    assert info.format == "SVG"


def test_an_svg_with_only_a_viewbox_is_still_described(tmp_path):
    from image_toolkit.discovery import SVG_EXTS

    path = tmp_path / "icon.svg"
    path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"/>')

    info = inspect_source(path, SVG_EXTS)

    assert info.error is None
    assert info.dimensions == (64, 64)


def test_an_svg_that_declares_no_size_says_so_without_failing(tmp_path):
    from image_toolkit.discovery import SVG_EXTS

    path = tmp_path / "sizeless.svg"
    path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"/>')

    info = inspect_source(path, SVG_EXTS)

    assert info.error is None
    assert info.dimensions is None
    assert info.format == "SVG"


def test_a_broken_svg_is_reported_as_broken(tmp_path):
    from image_toolkit.discovery import SVG_EXTS

    path = tmp_path / "broken.svg"
    path.write_bytes(b"this is not xml")

    info = inspect_source(path, SVG_EXTS)

    assert info.error
