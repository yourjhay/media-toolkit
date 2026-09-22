"""Guessing how long an encode will take, well enough to decide whether to ask.

The numbers are rough on purpose. Encode speed swings by an order of magnitude
between codecs, so this exists to tell a two second job from a four minute one,
not to predict either precisely.
"""

import pytest

from video_toolkit.speed import (
    SLOW_ENOUGH_TO_ASK,
    describe_wait,
    estimate_encode_seconds,
    is_slow,
)


def test_a_longer_clip_takes_longer():
    short = estimate_encode_seconds(10, "libx264")
    long = estimate_encode_seconds(600, "libx264")

    assert long > short


def test_vp9_is_expected_to_be_far_slower_than_h264():
    """Measured on this machine: vp9 ran at 0.6x realtime, libx264 at 5x."""
    assert estimate_encode_seconds(60, "libvpx-vp9") > estimate_encode_seconds(60, "libx264") * 3


def test_the_hardware_encoder_is_not_assumed_to_be_the_faster_one():
    """Measured, not assumed: on this machine libx264 encoded a 20s 720p clip in
    1.44s where h264_videotoolbox took 1.79s. Hardware encoders carry fixed
    setup costs that software presets avoid on short clips, so the numbers here
    follow the stopwatch rather than the intuition."""
    software = estimate_encode_seconds(60, "libx264")
    hardware = estimate_encode_seconds(60, "h264_videotoolbox")

    assert software < hardware
    assert hardware < estimate_encode_seconds(60, "libx265"), "still well ahead of x265"


def test_a_bigger_picture_takes_longer_than_a_smaller_one():
    hd = estimate_encode_seconds(60, "libx264", pixels=1920 * 1080)
    uhd = estimate_encode_seconds(60, "libx264", pixels=3840 * 2160)

    assert uhd > hd


def test_an_unknown_encoder_gives_no_estimate_rather_than_a_guess():
    assert estimate_encode_seconds(60, "some_new_encoder") is None


def test_an_unknown_duration_gives_no_estimate():
    assert estimate_encode_seconds(None, "libx264") is None
    assert estimate_encode_seconds(0, "libx264") is None


def test_a_quick_job_is_not_worth_interrupting_someone_over():
    assert is_slow(2) is False
    assert is_slow(SLOW_ENOUGH_TO_ASK - 1) is False


def test_a_long_job_is():
    assert is_slow(SLOW_ENOUGH_TO_ASK + 1) is True
    assert is_slow(600) is True


def test_an_unknown_length_counts_as_slow():
    """A download has no predictable length, and those are the ones worth backgrounding."""
    assert is_slow(None) is True


@pytest.mark.parametrize("seconds,expected", [
    (5, "a few seconds"),
    (45, "under a minute"),
    (90, "about 2 minutes"),
    (600, "about 10 minutes"),
])
def test_waits_are_described_the_way_people_say_them(seconds, expected):
    assert describe_wait(seconds) == expected


def test_an_unknown_wait_is_not_described_as_a_number():
    assert describe_wait(None) == "an unknown time"


# --- anchored to real measurements on this machine --------------------------

MEASURED = [
    # (label, duration, encoder, pixels, actual seconds observed)
    ("vp9 720p convert", 20.0, "libvpx-vp9", 1280 * 720, 31.5),
    ("x264 720p compress", 20.0, "libx264", 1280 * 720, 1.44),
    ("videotoolbox 720p compress", 20.0, "h264_videotoolbox", 1280 * 720, 1.79),
]


@pytest.mark.parametrize("label,duration,encoder,pixels,actual", MEASURED, ids=lambda v: str(v)[:20])
def test_the_estimate_lands_within_a_factor_of_three_of_reality(label, duration, encoder, pixels, actual):
    """Rough is fine. An order of magnitude out is not, because it decides
    whether someone is offered a way out of a half minute wait."""
    estimate = estimate_encode_seconds(duration, encoder, pixels)

    assert estimate is not None
    assert actual / 3 <= estimate <= actual * 3, f"{label}: estimated {estimate:.1f}s, actual {actual}s"


def test_the_vp9_case_that_was_missed_is_now_offered_a_background():
    """This one estimated "a few seconds" and took 31.5, so it was never offered."""
    estimate = estimate_encode_seconds(20.0, "libvpx-vp9", 1280 * 720)

    assert is_slow(estimate), f"a {estimate:.0f}s estimate should count as slow"
