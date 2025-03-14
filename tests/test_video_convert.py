from pathlib import Path

import pytest

from video_toolkit.formats import MP3, audio_postprocessors
from video_toolkit.download import resolve_output


# --- what to ask ffmpeg for ------------------------------------------------

def test_no_conversion_means_no_re_encoding_step():
    """Tags and art are still written; only the codec change is skipped."""
    steps = audio_postprocessors(None)

    assert all(step["key"] != "FFmpegExtractAudio" for step in steps)


def test_converting_asks_for_the_chosen_codec():
    steps = audio_postprocessors(MP3)

    assert steps[0]["key"] == "FFmpegExtractAudio"
    assert steps[0]["preferredcodec"] == "mp3"


def test_the_bitrate_is_carried_through():
    assert audio_postprocessors(MP3, quality="320")[0]["preferredquality"] == "320"


def test_a_codec_that_is_not_offered_is_rejected():
    with pytest.raises(ValueError):
        audio_postprocessors("flacc")


# --- where the file ended up ----------------------------------------------

def test_the_converted_path_is_preferred_over_the_downloaded_one():
    """After conversion the source is gone; reporting it would name a dead file."""
    info = {"requested_downloads": [{"filepath": "/out/song.mp3"}]}

    assert resolve_output(info, ["/out/song.webm"], "/out/song.webm", MP3) == Path("/out/song.mp3")


def test_without_that_key_the_extension_is_swapped_when_converting():
    assert resolve_output({}, ["/out/song.webm"], "/out/song.webm", MP3) == Path("/out/song.mp3")


def test_no_conversion_keeps_the_downloaded_path():
    assert resolve_output({}, ["/out/song.webm"], "/out/song.webm", None) == Path("/out/song.webm")


def test_the_fallback_is_used_when_no_hook_fired():
    assert resolve_output({}, [], "/out/song.m4a", None) == Path("/out/song.m4a")


def test_the_last_written_file_wins_over_earlier_ones():
    """A merged download reports each stream, then the merged result."""
    written = ["/out/song.f251.webm", "/out/song.f140.m4a", "/out/song.webm"]

    assert resolve_output({}, written, "x", None) == Path("/out/song.webm")


def test_an_empty_requested_downloads_list_does_not_break_things():
    assert resolve_output({"requested_downloads": []}, ["/out/a.webm"], "x", None) == Path("/out/a.webm")


# --- tags and cover art ----------------------------------------------------

def _keys(steps):
    return [step["key"] for step in steps]


def test_tags_and_cover_art_are_embedded_by_default():
    """An MP3 with no artist and no art is the complaint this answers."""
    steps = audio_postprocessors(MP3)

    assert "FFmpegMetadata" in _keys(steps)
    assert "EmbedThumbnail" in _keys(steps)


def test_the_audio_is_extracted_before_anything_is_written_into_it():
    steps = _keys(audio_postprocessors(MP3))

    assert steps.index("FFmpegExtractAudio") < steps.index("FFmpegMetadata")
    assert steps.index("FFmpegMetadata") < steps.index("EmbedThumbnail")


def test_tags_can_be_turned_off():
    assert "FFmpegMetadata" not in _keys(audio_postprocessors(MP3, tags=False))


def test_cover_art_can_be_turned_off():
    assert "EmbedThumbnail" not in _keys(audio_postprocessors(MP3, cover=False))


def test_tags_are_written_even_without_a_conversion():
    """A downloaded m4a deserves its artist just as much as an MP3 does."""
    steps = _keys(audio_postprocessors(None))

    assert "FFmpegExtractAudio" not in steps
    assert "FFmpegMetadata" in steps


def test_asking_for_nothing_at_all_gives_nothing():
    assert audio_postprocessors(None, tags=False, cover=False) == []


def test_the_thumbnail_must_be_fetched_for_it_to_be_embedded(tmp_path):
    """EmbedThumbnail has nothing to embed unless the image was downloaded."""
    from tests.test_video_download import FakeYoutubeDL
    from video_toolkit.download import download

    FakeYoutubeDL.instances.clear()
    download("https://example.com/watch?v=1", tmp_path, mode="audio",
             convert_to=MP3, ydl_factory=FakeYoutubeDL)

    assert FakeYoutubeDL.instances[0].options["writethumbnail"] is True


def test_the_thumbnail_is_not_fetched_when_no_cover_is_wanted(tmp_path):
    from tests.test_video_download import FakeYoutubeDL
    from video_toolkit.download import download

    FakeYoutubeDL.instances.clear()
    download("https://example.com/watch?v=1", tmp_path, mode="audio",
             convert_to=MP3, cover=False, ydl_factory=FakeYoutubeDL)

    assert FakeYoutubeDL.instances[0].options["writethumbnail"] is False
