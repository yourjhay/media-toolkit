from pathlib import Path

import pytest

from video_toolkit.download import (
    FAILED,
    OK,
    download,
    probe,
    read_progress,
)


# --- progress parsing (pure) -----------------------------------------------

def test_progress_uses_the_exact_total_when_there_is_one():
    update = read_progress({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 200})

    assert update.total == 200
    assert update.percent == pytest.approx(25.0)


def test_progress_falls_back_to_the_estimated_total():
    """Many sites only ever report an estimate."""
    update = read_progress(
        {"status": "downloading", "downloaded_bytes": 50, "total_bytes_estimate": 500}
    )

    assert update.total == 500
    assert update.percent == pytest.approx(10.0)


def test_progress_without_any_total_reports_no_percentage():
    update = read_progress({"status": "downloading", "downloaded_bytes": 50})

    assert update.total is None
    assert update.percent is None


def test_a_zero_total_does_not_divide_by_zero():
    update = read_progress({"status": "downloading", "downloaded_bytes": 0, "total_bytes": 0})

    assert update.percent is None


def test_the_finished_status_is_recognised():
    assert read_progress({"status": "finished", "filename": "v.mp4"}).finished is True
    assert read_progress({"status": "downloading", "downloaded_bytes": 1}).finished is False


def test_speed_and_eta_are_carried_through_when_present():
    update = read_progress(
        {"status": "downloading", "downloaded_bytes": 1, "speed": 1048576.0, "eta": 42}
    )

    assert update.speed == pytest.approx(1048576.0)
    assert update.eta == 42


# --- a stand-in for yt-dlp -------------------------------------------------

class FakeYoutubeDL:
    """Enough of YoutubeDL's surface to exercise our own logic offline."""

    instances = []

    def __init__(self, options):
        self.options = options
        self.info = {
            "title": "A Talk About Birds",
            "uploader": "Someone",
            "duration": 631,
            "ext": "mp4",
            "formats": [{"format_id": "18", "ext": "mp4", "height": 360,
                         "vcodec": "avc1", "acodec": "mp4a"}],
        }
        FakeYoutubeDL.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        if "broken" in url:
            raise RuntimeError("Video unavailable")
        if download:
            target = Path(self.prepare_filename(self.info))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"video data here")
            for hook in self.options.get("progress_hooks", []):
                hook({"status": "downloading", "downloaded_bytes": 8, "total_bytes": 15})
                hook({"status": "finished", "filename": str(target)})
        return dict(self.info)

    def prepare_filename(self, info):
        template = self.options["outtmpl"]
        if isinstance(template, dict):
            template = template["default"]
        return template % {"title": info["title"], "ext": info["ext"]}


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeYoutubeDL.instances.clear()


# --- probe -----------------------------------------------------------------

def test_probe_reports_what_the_video_is():
    info = probe("https://example.com/watch?v=1", ydl_factory=FakeYoutubeDL)

    assert info.title == "A Talk About Birds"
    assert info.uploader == "Someone"
    assert info.duration == 631
    assert info.error is None


def test_probe_never_downloads():
    probe("https://example.com/watch?v=1", ydl_factory=FakeYoutubeDL)

    assert FakeYoutubeDL.instances[0].options.get("skip_download", True)


def test_probe_reports_a_failure_rather_than_raising():
    info = probe("https://example.com/broken", ydl_factory=FakeYoutubeDL)

    assert info.error
    assert info.title is None


# --- download --------------------------------------------------------------

def test_a_download_writes_a_file_and_reports_where(tmp_path):
    result = download(
        "https://example.com/watch?v=1", tmp_path, ydl_factory=FakeYoutubeDL
    )

    assert result.status == OK
    assert result.path is not None and result.path.exists()
    assert result.title == "A Talk About Birds"


def test_the_file_lands_in_the_requested_folder(tmp_path):
    result = download("https://example.com/watch?v=1", tmp_path, ydl_factory=FakeYoutubeDL)

    assert result.path.parent == tmp_path


def test_a_failure_is_reported_rather_than_raised(tmp_path):
    result = download("https://example.com/broken", tmp_path, ydl_factory=FakeYoutubeDL)

    assert result.status == FAILED
    assert "unavailable" in result.detail.lower()
    assert result.path is None


def test_progress_reaches_the_caller(tmp_path):
    seen = []

    download(
        "https://example.com/watch?v=1", tmp_path,
        on_progress=seen.append, ydl_factory=FakeYoutubeDL,
    )

    assert any(u.percent is not None for u in seen)
    assert seen[-1].finished


def test_audio_mode_asks_for_audio(tmp_path):
    download("https://example.com/watch?v=1", tmp_path, mode="audio",
             ffmpeg=False, ydl_factory=FakeYoutubeDL)

    assert "bestaudio" in FakeYoutubeDL.instances[0].options["format"]


def test_without_ffmpeg_no_merge_is_requested(tmp_path):
    download("https://example.com/watch?v=1", tmp_path, mode="video",
             ffmpeg=False, ydl_factory=FakeYoutubeDL)

    assert "+" not in FakeYoutubeDL.instances[0].options["format"]


def test_a_height_limit_is_passed_along(tmp_path):
    download("https://example.com/watch?v=1", tmp_path, mode="video",
             ffmpeg=True, max_height=720, ydl_factory=FakeYoutubeDL)

    assert "720" in FakeYoutubeDL.instances[0].options["format"]


def test_the_output_template_keeps_files_inside_the_chosen_folder(tmp_path):
    download("https://example.com/watch?v=1", tmp_path, ydl_factory=FakeYoutubeDL)

    template = FakeYoutubeDL.instances[0].options["outtmpl"]
    assert str(tmp_path) in (template if isinstance(template, str) else template["default"])


# --- retrying ---------------------------------------------------------------

def test_transient_failures_are_retried_before_we_are_told(tmp_path):
    """yt-dlp's library defaults leave retries unset, so a single 403 gave up."""
    download("https://example.com/watch?v=1", tmp_path, ydl_factory=FakeYoutubeDL)
    options = FakeYoutubeDL.instances[0].options

    assert options["retries"] >= 3
    assert options["fragment_retries"] >= 3
    assert options["extractor_retries"] >= 1


def test_a_stalled_connection_does_not_hang_forever(tmp_path):
    download("https://example.com/watch?v=1", tmp_path, ydl_factory=FakeYoutubeDL)

    assert FakeYoutubeDL.instances[0].options["socket_timeout"] > 0
