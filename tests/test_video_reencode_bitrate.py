"""Re-encoding should not quietly quadruple the file.

Converting AV1 to H.264 for playability turned 6.1 MB into 27 MB, because the
hardware encoder picks its own very generous rate when not told otherwise.
"""

import pytest

from video_toolkit.bitrate import MIN_VIDEO_BITRATE, reencode_bitrate


def test_h264_is_given_more_than_the_source_because_it_is_less_efficient():
    """AV1 at 3 Mbps needs roughly double that in H.264 to look the same."""
    assert reencode_bitrate(3_000_000) > 3_000_000


def test_it_does_not_hand_out_an_absurd_rate():
    assert reencode_bitrate(3_000_000) < 3_000_000 * 4


def test_a_high_bitrate_source_is_capped():
    assert reencode_bitrate(80_000_000) <= 20_000_000


def test_a_tiny_source_still_gets_something_watchable():
    assert reencode_bitrate(20_000) >= MIN_VIDEO_BITRATE


def test_an_unknown_source_bitrate_gives_none_so_the_encoder_decides():
    assert reencode_bitrate(None) is None


@pytest.mark.parametrize("bad", [0, -1])
def test_a_nonsense_bitrate_is_treated_as_unknown(bad):
    assert reencode_bitrate(bad) is None


def test_the_result_is_a_whole_number():
    assert isinstance(reencode_bitrate(3_000_000), int)
