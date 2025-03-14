from pathlib import Path

import pytest

from video_toolkit.media import MediaInfo
from video_toolkit.operations import FAILED, OK, OVER, SKIPPED
from video_toolkit.tasks import compress_video, convert_video, trim_video


def _info(tmp_path, **over):
    base = dict(
        path=tmp_path / "clip.mkv", size_bytes=10_000_000, duration=120.0,
        width=1920, height=1080, video_codec="h264", audio_codec="aac",
        audio_bitrate=128_000,
    )
    base.update(over)
    return MediaInfo(**base)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "clip.mkv"
    path.write_bytes(b"pretend this is a video" * 100)
    return path


def _runner(writes: int = 5000, ok: bool = True, message: str = "boom"):
    """Stands in for ffmpeg: writes an output of a chosen size."""
    captured = {}

    def run(args, duration, on_progress):
        captured["args"] = args
        if not ok:
            return False, message
        Path(args[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(args[-1]).write_bytes(b"x" * writes)
        return True, ""

    run.captured = captured
    return run


# --- convert ---------------------------------------------------------------

def test_converting_writes_the_new_container(source, tmp_path):
    run = _runner()

    result = convert_video(source, tmp_path / "out", "mp4",
                           probe=lambda p: _info(tmp_path), runner=run)

    assert result.status == OK
    assert result.output.name == "clip.mp4"
    assert result.output.exists()


def test_a_repackage_is_reported_as_lossless(source, tmp_path):
    result = convert_video(source, tmp_path / "out", "mkv",
                           probe=lambda p: _info(tmp_path), runner=_runner())

    assert result.lossless
    assert "untouched" in result.detail


def test_a_conversion_that_must_re_encode_says_so(source, tmp_path):
    result = convert_video(source, tmp_path / "out", "webm",
                           probe=lambda p: _info(tmp_path), runner=_runner())

    assert not result.lossless
    assert "re-encoding" in result.detail


def test_an_unreadable_source_is_reported(source, tmp_path):
    result = convert_video(source, tmp_path / "out", "mp4",
                           probe=lambda p: _info(tmp_path, error="broken"), runner=_runner())

    assert result.status == FAILED


def test_an_ffmpeg_failure_is_reported_not_raised(source, tmp_path):
    result = convert_video(source, tmp_path / "out", "mp4",
                           probe=lambda p: _info(tmp_path),
                           runner=_runner(ok=False, message="Invalid data"))

    assert result.status == FAILED
    assert "Invalid data" in result.detail


def test_existing_output_is_left_alone_by_default(source, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "clip.mp4").write_bytes(b"keep me")

    result = convert_video(source, out_dir, "mp4",
                           probe=lambda p: _info(tmp_path), runner=_runner())

    assert result.status == SKIPPED
    assert (out_dir / "clip.mp4").read_bytes() == b"keep me"


def test_it_refuses_to_write_over_the_source(source, tmp_path):
    original = source.read_bytes()

    result = convert_video(source, source.parent, "mkv",
                           probe=lambda p: _info(tmp_path), runner=_runner())

    assert result.status == FAILED
    assert source.read_bytes() == original


# --- compress --------------------------------------------------------------

def test_compressing_to_a_target_reports_success_when_it_fits(source, tmp_path):
    """Five seconds into 500 KB is a target that can actually be met."""
    result = compress_video(source, tmp_path / "out", target_bytes=500_000,
                            probe=lambda p: _info(tmp_path, duration=5.0),
                            runner=_runner(writes=400_000))

    assert result.status == OK
    assert result.output_bytes == 400_000


def test_overshooting_the_target_is_reported_honestly(source, tmp_path):
    """One-pass encoding lands near the target, not exactly on it."""
    result = compress_video(source, tmp_path / "out", target_bytes=500_000,
                            probe=lambda p: _info(tmp_path, duration=5.0),
                            runner=_runner(writes=600_000))

    assert result.status == OVER
    assert "over" in result.detail.lower()


def test_a_target_too_small_for_the_clip_is_refused_before_encoding(source, tmp_path):
    """Two minutes into 100 bytes is impossible; say so without burning CPU."""
    run = _runner()

    result = compress_video(source, tmp_path / "out", target_bytes=100,
                            probe=lambda p: _info(tmp_path), runner=run)

    assert result.status == FAILED
    assert "args" not in run.captured, "nothing should have been encoded"


def test_a_clip_of_unknown_length_cannot_be_compressed_to_a_size(source, tmp_path):
    result = compress_video(source, tmp_path / "out", target_bytes=1_000_000,
                            probe=lambda p: _info(tmp_path, duration=None), runner=_runner())

    assert result.status == FAILED
    assert "length" in result.detail.lower()


def test_a_silent_clip_compresses_without_audio(source, tmp_path):
    run = _runner()

    compress_video(source, tmp_path / "out", target_bytes=500_000,
                   probe=lambda p: _info(tmp_path, duration=5.0, audio_codec=None,
                                         audio_bitrate=None),
                   runner=run)

    assert "-an" in run.captured["args"]


# --- trim ------------------------------------------------------------------

def test_trimming_writes_a_clip(source, tmp_path):
    result = trim_video(source, tmp_path / "out", start=10, end=20,
                        probe=lambda p: _info(tmp_path), runner=_runner())

    assert result.status == OK
    assert result.output.exists()


def test_a_fast_trim_is_reported_as_lossless(source, tmp_path):
    result = trim_video(source, tmp_path / "out", start=10, end=20, precise=False,
                        probe=lambda p: _info(tmp_path), runner=_runner())

    assert result.lossless
    assert "keyframe" in result.detail.lower()


def test_a_precise_trim_says_it_re_encodes(source, tmp_path):
    result = trim_video(source, tmp_path / "out", start=10, end=20, precise=True,
                        probe=lambda p: _info(tmp_path), runner=_runner())

    assert not result.lossless


def test_a_range_beyond_the_clip_is_pulled_back(source, tmp_path):
    run = _runner()

    trim_video(source, tmp_path / "out", start=10, end=9999,
               probe=lambda p: _info(tmp_path), runner=run)

    args = run.captured["args"]
    # A fast cut asks for a duration: from 10s to the 120s end is 110 seconds.
    assert float(args[args.index("-t") + 1]) == 110.0


def test_a_start_past_the_end_of_the_clip_is_refused(source, tmp_path):
    result = trim_video(source, tmp_path / "out", start=500, end=600,
                        probe=lambda p: _info(tmp_path), runner=_runner())

    assert result.status == FAILED
