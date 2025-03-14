from pathlib import Path

import pytest

from video_toolkit.formats import MP3, audio_postprocessors
from video_toolkit.download import resolve_output


# --- what to ask ffmpeg for ------------------------------------------------

def test_no_conversion_means_no_postprocessors():
    assert audio_postprocessors(None) == []


def test_converting_asks_for_the_chosen_codec():
    steps = audio_postprocessors(MP3)

    assert len(steps) == 1
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
