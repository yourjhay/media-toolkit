import pytest

from video_toolkit.bitrate import MIN_VIDEO_BITRATE, SAFETY_MARGIN, target_bitrate


def test_the_video_gets_what_is_left_after_the_audio():
    """60s, 10 MB target, 128 kbps audio."""
    video = target_bitrate(duration=60, target_bytes=10 * 1024 * 1024, audio_bitrate=128_000)

    total = 10 * 1024 * 1024 * 8 * SAFETY_MARGIN
    expected = (total - 128_000 * 60) / 60
    assert video == pytest.approx(expected, rel=0.01)


def test_it_aims_slightly_under_the_target():
    """Container overhead is real, so hitting the number exactly overshoots it."""
    video = target_bitrate(duration=60, target_bytes=10 * 1024 * 1024, audio_bitrate=0)

    naive = 10 * 1024 * 1024 * 8 / 60
    assert video < naive


def test_a_longer_clip_at_the_same_size_gets_less_bitrate():
    small = target_bitrate(duration=600, target_bytes=25 * 1024 * 1024)
    large = target_bitrate(duration=60, target_bytes=25 * 1024 * 1024)

    assert small < large


def test_a_target_the_audio_alone_would_exceed_is_rejected():
    with pytest.raises(ValueError) as excinfo:
        target_bitrate(duration=600, target_bytes=1024 * 1024, audio_bitrate=128_000)

    assert "audio" in str(excinfo.value).lower()


def test_a_target_too_small_to_be_watchable_is_rejected():
    """An hour into 20 MB: the audio fits, but what is left is unwatchable."""
    with pytest.raises(ValueError) as excinfo:
        target_bitrate(duration=3600, target_bytes=20 * 1024 * 1024, audio_bitrate=32_000)

    message = str(excinfo.value)
    assert str(MIN_VIDEO_BITRATE // 1000) in message
    assert "audio alone" not in message, "this is the video-bitrate limit, not the audio one"


def test_the_audio_limit_is_reported_before_the_video_one():
    """When both would fail, the audio is the more useful thing to be told."""
    with pytest.raises(ValueError) as excinfo:
        target_bitrate(duration=3600, target_bytes=2 * 1024 * 1024, audio_bitrate=64_000)

    assert "audio alone" in str(excinfo.value)


@pytest.mark.parametrize("duration", [0, -1])
def test_a_clip_with_no_length_is_rejected(duration):
    with pytest.raises(ValueError):
        target_bitrate(duration=duration, target_bytes=10 * 1024 * 1024)


def test_a_target_of_nothing_is_rejected():
    with pytest.raises(ValueError):
        target_bitrate(duration=60, target_bytes=0)


def test_the_result_is_a_whole_number_of_bits_per_second():
    assert isinstance(target_bitrate(duration=60, target_bytes=10 * 1024 * 1024), int)
