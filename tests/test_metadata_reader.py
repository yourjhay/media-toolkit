import pytest

from image_toolkit.metadata import (
    decode_coordinates,
    format_coordinates,
    maps_link,
    read_metadata,
)


def test_northern_and_eastern_coordinates_are_positive():
    gps = {1: "N", 2: (14.0, 35.0, 30.0), 3: "E", 4: (121.0, 0.0, 0.0)}

    latitude, longitude = decode_coordinates(gps)

    assert latitude == pytest.approx(14.591666, abs=1e-5)
    assert longitude == pytest.approx(121.0, abs=1e-5)


def test_southern_and_western_coordinates_are_negative():
    """The hemisphere letters are the only thing carrying the sign."""
    gps = {1: "S", 2: (33.0, 51.0, 0.0), 3: "W", 4: (151.0, 12.0, 0.0)}

    latitude, longitude = decode_coordinates(gps)

    assert latitude < 0 and longitude < 0
    assert latitude == pytest.approx(-33.85, abs=1e-5)


def test_coordinates_are_none_when_the_block_is_incomplete():
    assert decode_coordinates({1: "N", 2: (14.0, 35.0, 0.0)}) is None
    assert decode_coordinates({}) is None


def test_malformed_coordinates_do_not_raise():
    assert decode_coordinates({1: "N", 2: "rubbish", 3: "E", 4: (1.0, 2.0, 3.0)}) is None


def test_coordinates_are_formatted_for_a_human():
    assert format_coordinates(14.591666, 121.0) == "14°35'30\"N, 121°00'00\"E"


def test_southern_western_formatting_uses_the_right_letters():
    assert format_coordinates(-33.85, -151.2) == "33°51'00\"S, 151°12'00\"W"


def test_a_maps_link_is_offered_for_the_coordinates():
    assert maps_link(14.5, 121.0) == "https://www.google.com/maps?q=14.5,121.0"


def test_reading_a_photo_reports_its_basic_shape(make_jpg):
    data = read_metadata(make_jpg("holiday.jpg", width=640, height=480))

    assert data.name == "holiday.jpg"
    assert data.dimensions == (640, 480)
    assert data.format == "JPEG"
    assert data.size_bytes > 0
    assert data.error is None


def test_reading_a_phone_photo_surfaces_the_camera_and_date(
    make_heic, exif_with_location
):
    data = read_metadata(make_heic("phone.heic", exif=exif_with_location))

    labels = {field.label: field.value for field in data.fields}
    assert labels["Camera"] == "Apple iPhone 15 Pro"
    assert "2026" in labels["Taken"]


def test_location_is_reported_and_flagged_as_sensitive(make_heic, exif_with_location):
    data = read_metadata(make_heic("phone.heic", exif=exif_with_location))

    location = [f for f in data.fields if f.label == "Location"]
    assert len(location) == 1
    assert "N" in location[0].value and "E" in location[0].value
    assert location[0].sensitive is True
    assert data.has_location is True


def test_a_photo_without_location_says_so(make_jpg):
    data = read_metadata(make_jpg("plain.jpg"))

    assert data.has_location is False
    assert not [f for f in data.fields if f.sensitive]


def test_a_photo_with_no_metadata_at_all_still_reports_its_file_facts(make_png):
    data = read_metadata(make_png("chart.png", width=320, height=240))

    assert data.dimensions == (320, 240)
    assert data.error is None
    assert not data.has_location


def test_an_unreadable_file_reports_the_problem_rather_than_raising(touch):
    data = read_metadata(touch("broken.jpg", b"not an image"))

    assert data.error
    assert data.dimensions is None


def test_the_tag_count_is_reported(make_heic, exif_with_location):
    data = read_metadata(make_heic("phone.heic", exif=exif_with_location))

    assert data.tag_count > 0


def test_fields_never_contain_empty_values(make_heic, exif_with_location):
    """An empty row is noise; a field with nothing in it should be omitted."""
    data = read_metadata(make_heic("phone.heic", exif=exif_with_location))

    assert all(field.value.strip() for field in data.fields)


def test_exif_dates_are_shown_the_way_people_write_them():
    """EXIF uses colons in the date part, which reads as a time to everyone else."""
    from image_toolkit.metadata import pretty_datetime

    assert pretty_datetime("2026:09:21 14:00:00") == "2026-09-21 14:00"


def test_a_date_without_seconds_survives():
    from image_toolkit.metadata import pretty_datetime

    assert pretty_datetime("2026:09:21 14:00") == "2026-09-21 14:00"


def test_an_unrecognised_date_is_passed_through_unchanged():
    from image_toolkit.metadata import pretty_datetime

    assert pretty_datetime("sometime last year") == "sometime last year"
    assert pretty_datetime("") == ""


def test_the_maps_link_is_not_absurdly_precise():
    """Six decimal places is about 10cm; the raw float is 15 digits of noise."""
    assert maps_link(14.591666666666667, 121.0) == "https://www.google.com/maps?q=14.591667,121.0"
