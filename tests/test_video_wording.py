import pytest

from video_toolkit.formats import AUDIO, VIDEO
from video_toolkit.planning import download_noun


def test_one_video_reads_as_a_video():
    assert download_noun(VIDEO, 1) == "1 video"


def test_several_videos_are_pluralised():
    assert download_noun(VIDEO, 3) == "3 videos"


def test_audio_mode_does_not_call_it_a_video():
    """The whole point of audio mode is that no video is being kept."""
    assert download_noun(AUDIO, 1) == "1 audio track"


def test_several_audio_tracks_are_pluralised():
    assert download_noun(AUDIO, 12) == "12 audio tracks"


def test_zero_is_pluralised_too():
    assert download_noun(VIDEO, 0) == "0 videos"
    assert download_noun(AUDIO, 0) == "0 audio tracks"


def test_an_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        download_noun("hologram", 1)


@pytest.mark.parametrize("mode", [VIDEO, AUDIO])
def test_every_mode_the_toolkit_offers_has_wording(mode):
    assert download_noun(mode, 1)
