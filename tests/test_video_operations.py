from pathlib import Path

import pytest

from video_toolkit.containers import plan_conversion
from video_toolkit.operations import (
    build_compress_args,
    build_convert_args,
    build_mute_args,
    build_trim_args,
)

SRC = Path("/in/clip.mkv")
OUT = Path("/out/clip.mp4")


def _pairs(args):
    """The flags and their values, for order-independent assertions."""
    return {args[i]: args[i + 1] for i in range(len(args) - 1)}


# --- convert ---------------------------------------------------------------

def test_a_repackage_copies_both_streams():
    args = build_convert_args(SRC, OUT, plan_conversion("h264", "aac", "mp4"))

    assert _pairs(args)["-c:v"] == "copy"
    assert _pairs(args)["-c:a"] == "copy"


def test_only_the_offending_stream_is_encoded():
    args = build_convert_args(SRC, OUT, plan_conversion("h264", "opus", "mp4"))

    assert _pairs(args)["-c:v"] == "copy"
    assert _pairs(args)["-c:a"] == "aac"


def test_a_file_without_audio_does_not_ask_for_an_audio_codec():
    args = build_convert_args(SRC, OUT, plan_conversion("h264", None, "mp4"))

    assert "-c:a" not in args


def test_mp4_output_is_made_streamable():
    """Without this the index sits at the end and the file cannot start playing."""
    args = build_convert_args(SRC, OUT, plan_conversion("h264", "aac", "mp4"))

    assert "+faststart" in " ".join(args)


def test_the_source_and_destination_are_both_present():
    args = build_convert_args(SRC, OUT, plan_conversion("h264", "aac", "mp4"))

    assert str(SRC) in args
    assert args[-1] == str(OUT)


# --- compress --------------------------------------------------------------

def test_compression_sets_the_video_bitrate_it_was_given():
    args = build_compress_args(SRC, OUT, video_bitrate=800_000, audio_bitrate=128_000,
                               video_encoder="libx264")

    assert _pairs(args)["-b:v"] == "800000"
    assert _pairs(args)["-b:a"] == "128000"


def test_compression_caps_the_peak_so_the_target_is_not_blown():
    args = build_compress_args(SRC, OUT, video_bitrate=800_000, audio_bitrate=128_000,
                               video_encoder="libx264")
    pairs = _pairs(args)

    assert int(pairs["-maxrate"]) > 800_000
    assert "-bufsize" in pairs


def test_compression_uses_the_encoder_it_was_given():
    args = build_compress_args(SRC, OUT, video_bitrate=1, audio_bitrate=1,
                               video_encoder="h264_videotoolbox")

    assert _pairs(args)["-c:v"] == "h264_videotoolbox"


def test_a_silent_source_is_compressed_without_an_audio_track():
    args = build_compress_args(SRC, OUT, video_bitrate=1, audio_bitrate=None,
                               video_encoder="libx264")

    assert "-an" in args
    assert "-b:a" not in args


# --- trim ------------------------------------------------------------------

def test_a_fast_trim_copies_the_streams():
    args = build_trim_args(SRC, OUT, start=10, end=20, precise=False)

    assert _pairs(args)["-c"] == "copy"


def test_a_fast_trim_seeks_before_opening_the_input():
    """Seeking first is what makes it instant; it is also why it snaps to a keyframe."""
    args = build_trim_args(SRC, OUT, start=10, end=20, precise=False)

    assert args.index("-ss") < args.index("-i")


def test_a_precise_trim_seeks_after_opening_and_re_encodes():
    args = build_trim_args(SRC, OUT, start=10, end=20, precise=True,
                           video_encoder="libx264")

    assert args.index("-ss") > args.index("-i")
    assert _pairs(args)["-c:v"] == "libx264"


def test_the_range_reaches_the_command():
    args = build_trim_args(SRC, OUT, start=10, end=20, precise=False)
    pairs = _pairs(args)

    assert float(pairs["-ss"]) == 10.0
    assert float(pairs["-t"]) == 10.0


def test_a_backwards_range_is_rejected():
    with pytest.raises(ValueError):
        build_trim_args(SRC, OUT, start=20, end=10, precise=False)


# --- shared shape ----------------------------------------------------------

@pytest.mark.parametrize("args", [
    build_convert_args(SRC, OUT, plan_conversion("h264", "aac", "mp4")),
    build_compress_args(SRC, OUT, 1, 1, "libx264"),
    build_trim_args(SRC, OUT, 0, 1, precise=False),
])
def test_every_command_reports_progress_and_stays_quiet(args):
    assert "-progress" in args
    assert "-nostats" in args
    assert args[-1] == str(OUT)


def test_a_fast_trim_asks_for_a_duration_not_an_end_time():
    """With -ss before -i, ffmpeg measures -to from the seek point, so asking
    to stop at 20 while starting at 10 yields twenty seconds, not ten. A
    duration is unambiguous either way."""
    args = build_trim_args(SRC, OUT, start=10, end=20, precise=False)
    pairs = _pairs(args)

    assert "-to" not in pairs
    assert float(pairs["-t"]) == 10.0


def test_a_precise_trim_may_use_absolute_times():
    """Seeking after the input keeps the original timeline, so -to is correct."""
    args = build_trim_args(SRC, OUT, start=10, end=20, precise=True)
    pairs = _pairs(args)

    assert float(pairs["-ss"]) == 10.0
    assert float(pairs["-to"]) == 20.0


def test_a_re_encoding_conversion_is_given_a_bitrate_when_one_is_known():
    """Left to itself the hardware encoder picks a very generous rate."""
    args = build_convert_args(SRC, OUT, plan_conversion("vp9", "opus", "mp4"),
                              video_bitrate=6_000_000)

    assert _pairs(args)["-b:v"] == "6000000"


def test_a_repackage_is_never_given_a_bitrate():
    """Nothing is being encoded, so a rate would be meaningless."""
    args = build_convert_args(SRC, OUT, plan_conversion("h264", "aac", "mp4"),
                              video_bitrate=6_000_000)

    assert "-b:v" not in args


def test_an_unknown_bitrate_leaves_the_encoder_to_choose():
    args = build_convert_args(SRC, OUT, plan_conversion("vp9", "opus", "mp4"),
                              video_bitrate=None)

    assert "-b:v" not in args


# --- mute ------------------------------------------------------------------

def test_muting_drops_the_sound():
    args = build_mute_args(SRC, OUT)

    assert "-an" in args


def test_muting_copies_the_picture_rather_than_re_encoding_it():
    args = build_mute_args(SRC, OUT)

    assert _pairs(args)["-c"] == "copy"
    assert "-c:v" not in args


def test_a_muted_mp4_is_still_made_streamable():
    args = build_mute_args(SRC, OUT)

    assert "+faststart" in " ".join(args)
    assert args[-1] == str(OUT)
