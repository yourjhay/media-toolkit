import json

import pytest

from video_toolkit.media import ProgressReader, probe_media

SAMPLE = {
    "format": {"duration": "124.5", "size": "10485760", "bit_rate": "673000"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
         "avg_frame_rate": "30000/1001"},
        {"codec_type": "audio", "codec_name": "aac", "bit_rate": "128000"},
    ],
}


def _runner(payload):
    def run(args):
        return json.dumps(payload)
    return run


def test_it_reads_the_length_and_the_streams(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")

    info = probe_media(path, runner=_runner(SAMPLE))

    assert info.duration == pytest.approx(124.5)
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.width == 1920 and info.height == 1080
    assert info.audio_bitrate == 128_000
    assert info.error is None


def test_a_file_with_no_audio_reports_none(tmp_path):
    path = tmp_path / "silent.mp4"
    path.write_bytes(b"x")
    payload = {"format": {"duration": "10"}, "streams": [SAMPLE["streams"][0]]}

    info = probe_media(path, runner=_runner(payload))

    assert info.audio_codec is None
    assert info.audio_bitrate is None


def test_a_file_with_no_video_reports_none(tmp_path):
    path = tmp_path / "sound.m4a"
    path.write_bytes(b"x")
    payload = {"format": {"duration": "10"}, "streams": [SAMPLE["streams"][1]]}

    info = probe_media(path, runner=_runner(payload))

    assert info.video_codec is None


def test_an_unknown_duration_is_none_rather_than_a_guess(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")

    info = probe_media(path, runner=_runner({"format": {}, "streams": []}))

    assert info.duration is None


def test_the_size_comes_from_disk_not_from_ffprobe(tmp_path):
    """ffprobe can be wrong or absent about size; the filesystem cannot."""
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"0123456789")

    info = probe_media(path, runner=_runner(SAMPLE))

    assert info.size_bytes == 10


def test_unreadable_output_is_reported_not_raised(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")

    info = probe_media(path, runner=lambda args: "this is not json")

    assert info.error


def test_a_failing_probe_is_reported_not_raised(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")

    def boom(args):
        raise RuntimeError("ffprobe exploded")

    info = probe_media(path, runner=boom)

    assert info.error and "exploded" in info.error


def test_ffprobe_refusing_a_file_gives_its_own_reason(tmp_path):
    """Not the whole command line it was run with, which buries the reason."""
    import subprocess

    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")

    def refuse(args):
        raise subprocess.CalledProcessError(
            1, ["ffprobe", *args],
            stderr=f"[mov @ 0x1] moov atom not found\n{path}: Invalid data found when processing input\n",
        )

    info = probe_media(path, runner=refuse)

    assert info.error == "Invalid data found when processing input"


def test_a_missing_file_is_reported(tmp_path):
    info = probe_media(tmp_path / "gone.mp4", runner=_runner(SAMPLE))

    assert info.error


# --- ffmpeg progress -------------------------------------------------------

def test_progress_is_only_emitted_once_a_block_completes():
    """ffmpeg sends key=value lines, then a progress= line closing the block."""
    reader = ProgressReader(duration=100)

    assert reader.feed("frame=25") is None
    assert reader.feed("out_time_us=10000000") is None
    update = reader.feed("progress=continue")

    assert update is not None
    assert update.percent == pytest.approx(10.0)


def test_progress_reports_completion_at_the_end():
    reader = ProgressReader(duration=100)
    reader.feed("out_time_us=100000000")
    update = reader.feed("progress=end")

    assert update.finished
    assert update.percent == pytest.approx(100.0)


def test_progress_never_claims_more_than_complete():
    """Encoders overshoot the reported duration slightly; 103% reads as a bug."""
    reader = ProgressReader(duration=10)
    reader.feed("out_time_us=11000000")
    update = reader.feed("progress=continue")

    assert update.percent == 100.0


def test_progress_without_a_known_duration_has_no_percentage():
    reader = ProgressReader(duration=None)
    reader.feed("out_time_us=5000000")
    update = reader.feed("progress=continue")

    assert update.percent is None
    assert update.seconds == pytest.approx(5.0)


def test_the_speed_figure_is_carried_through():
    reader = ProgressReader(duration=100)
    reader.feed("speed=2.5x")
    update = reader.feed("progress=continue")

    assert update.speed == pytest.approx(2.5)


def test_rubbish_lines_are_ignored():
    reader = ProgressReader(duration=100)

    assert reader.feed("") is None
    assert reader.feed("no equals sign here") is None
    assert reader.feed("speed=N/A") is None
    update = reader.feed("progress=continue")
    assert update.speed is None


def test_the_video_bitrate_is_read_when_the_stream_reports_it(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")
    payload = {
        "format": {"duration": "10", "bit_rate": "3200000"},
        "streams": [
            {"codec_type": "video", "codec_name": "av1", "bit_rate": "3100000"},
            {"codec_type": "audio", "codec_name": "aac", "bit_rate": "128000"},
        ],
    }

    info = probe_media(path, runner=_runner(payload))

    assert info.video_bitrate == 3_100_000


def test_a_missing_video_bitrate_falls_back_to_the_container_minus_the_audio(tmp_path):
    """Many files only report an overall rate; the video is nearly all of it."""
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")
    payload = {
        "format": {"duration": "10", "bit_rate": "3200000"},
        "streams": [
            {"codec_type": "video", "codec_name": "av1"},
            {"codec_type": "audio", "codec_name": "aac", "bit_rate": "128000"},
        ],
    }

    info = probe_media(path, runner=_runner(payload))

    assert info.video_bitrate == 3_200_000 - 128_000


def test_no_bitrate_anywhere_is_none_rather_than_a_guess(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")

    info = probe_media(path, runner=_runner({"format": {}, "streams": []}))

    assert info.video_bitrate is None
