import pytest

from video_toolkit.timecode import format_timecode, parse_timecode, validate_range


@pytest.mark.parametrize("text,seconds", [
    ("90", 90.0),
    ("1:30", 90.0),
    ("0:01:30", 90.0),
    ("1:02:03", 3723.0),
    ("1:30.5", 90.5),
    ("00:00:00", 0.0),
])
def test_common_ways_of_writing_a_time(text, seconds):
    assert parse_timecode(text) == pytest.approx(seconds)


def test_surrounding_space_is_ignored():
    assert parse_timecode("  2:00  ") == 120.0


@pytest.mark.parametrize("bad", ["", "   ", "abc", "1:2:3:4", "-5", "1:-2", "::"])
def test_nonsense_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_timecode(bad)


def test_minutes_and_seconds_beyond_sixty_are_rejected():
    """1:90 is ambiguous — almost certainly a typo for 2:30."""
    with pytest.raises(ValueError):
        parse_timecode("1:90")


def test_a_bare_number_may_exceed_sixty():
    """Plain seconds have no such ambiguity."""
    assert parse_timecode("240") == 240.0


@pytest.mark.parametrize("seconds,text", [
    (0, "0:00"),
    (90, "1:30"),
    (3723, "1:02:03"),
    (59.4, "0:59"),
])
def test_times_are_written_back_the_way_people_read_them(seconds, text):
    assert format_timecode(seconds) == text


def test_a_valid_range_is_accepted():
    assert validate_range(10, 20, duration=60) == (10.0, 20.0)


def test_an_end_before_the_start_is_rejected():
    with pytest.raises(ValueError):
        validate_range(20, 10, duration=60)


def test_an_empty_range_is_rejected():
    with pytest.raises(ValueError):
        validate_range(10, 10, duration=60)


def test_a_start_past_the_end_of_the_clip_is_rejected():
    with pytest.raises(ValueError):
        validate_range(70, 80, duration=60)


def test_an_end_past_the_clip_is_pulled_back_to_its_length():
    """Asking for more than there is should give everything there is."""
    assert validate_range(10, 999, duration=60) == (10.0, 60.0)


def test_no_end_given_means_run_to_the_end():
    assert validate_range(10, None, duration=60) == (10.0, 60.0)


def test_an_unknown_duration_trusts_the_numbers_given():
    assert validate_range(10, 20, duration=None) == (10.0, 20.0)
