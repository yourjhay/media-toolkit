"""vidkit without the menu, as a script or an AI agent drives it.

The operations themselves are tested elsewhere. These check that each
argument reaches the operation it was meant for, that the output can be read
by a program, and that the exit code says whether it worked.
"""

import json
from pathlib import Path

import pytest

from video_toolkit import cli
from video_toolkit.download import DownloadResult, VideoInfo
from video_toolkit.media import MediaInfo
from video_toolkit.operations import FAILED, OK, SKIPPED, EncodeResult


@pytest.fixture(autouse=True)
def ffmpeg_present(monkeypatch):
    monkeypatch.setattr(cli, "ffmpeg_available", lambda: True)


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "clip.mov"
    path.write_bytes(b"pretend this is a video")
    return path


def _info(path, **over):
    base = dict(path=Path(path), size_bytes=1000, duration=60.0, width=1920, height=1080,
                video_codec="h264", audio_codec="aac")
    base.update(over)
    return MediaInfo(**base)


def _fake_task(status=OK, detail="done"):
    """Stands in for one of the tasks, noting how it was called."""
    calls = []

    def task(src, dest_dir, *args, **kwargs):
        calls.append({"src": Path(src), "dest_dir": Path(dest_dir), "args": args, **kwargs})
        out = Path(dest_dir) / f"{Path(src).stem}-out{Path(src).suffix}"
        return EncodeResult(Path(src), out if status == OK else None, status, 1000,
                            800 if status == OK else 0, detail)

    task.calls = calls
    return task


def _run(capsys, *argv):
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _json(capsys, *argv):
    code, out, _ = _run(capsys, *argv, "--json")
    return code, json.loads(out)


# --- sizes and qualities ---------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("25MB", 25 * 1024 * 1024),
    ("25mb", 25 * 1024 * 1024),
    ("25M", 25 * 1024 * 1024),
    ("25", 25 * 1024 * 1024),
    ("1.5GB", int(1.5 * 1024 ** 3)),
    ("800KB", 800 * 1024),
    ("800 KB", 800 * 1024),
])
def test_sizes_are_read_the_way_people_write_them(text, expected):
    assert cli.parse_size(text) == expected


@pytest.mark.parametrize("text", ["", "MB", "25 parsecs", "-5MB", "0"])
def test_a_size_that_cannot_be_read_is_refused(text):
    with pytest.raises(ValueError):
        cli.parse_size(text)


def test_best_quality_means_no_cap():
    assert cli.parse_quality("best") is None
    assert cli.parse_quality("1080") == 1080
    assert cli.parse_quality("1080p") == 1080


def test_a_quality_that_is_not_a_height_is_refused():
    with pytest.raises(ValueError):
        cli.parse_quality("high")


# --- usage -----------------------------------------------------------------

def test_no_command_prints_the_help_and_fails(capsys):
    code, out, err = _run(capsys)

    assert code == cli.EXIT_USAGE
    assert "mute" in out + err


def test_a_missing_file_is_a_usage_error(capsys, tmp_path):
    code, _, err = _run(capsys, "mute", str(tmp_path / "nope.mov"))

    assert code == cli.EXIT_USAGE
    assert "nope.mov" in err


def test_compress_takes_a_file_not_a_folder(capsys, tmp_path):
    code, _, err = _run(capsys, "compress", str(tmp_path), "--size", "25MB")

    assert code == cli.EXIT_USAGE
    assert "folder" in err


def test_json_may_come_before_or_after_the_command(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "mute_video", _fake_task())

    before = json.loads(_run(capsys, "--json", "mute", str(clip))[1])
    after = json.loads(_run(capsys, "mute", str(clip), "--json")[1])

    assert before["results"][0]["status"] == after["results"][0]["status"] == OK


def test_local_work_without_ffmpeg_says_how_to_get_it(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "ffmpeg_available", lambda: False)

    code, _, err = _run(capsys, "mute", str(clip))

    assert code == cli.EXIT_FAILED
    assert "brew install ffmpeg" in err


# --- what comes back -------------------------------------------------------

def test_json_output_names_the_file_produced(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "mute_video", _fake_task())

    code, report = _json(capsys, "mute", str(clip))

    assert code == cli.EXIT_OK
    assert report["command"] == "mute"
    assert report["ok"] is True
    row = report["results"][0]
    assert row["source"] == str(clip)
    assert row["output"].endswith("clip-out.mov")
    assert row["source_bytes"] == 1000 and row["output_bytes"] == 800


def test_a_failure_sets_the_exit_code_and_says_why(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "mute_video", _fake_task(FAILED, "Invalid data"))

    code, report = _json(capsys, "mute", str(clip))

    assert code == cli.EXIT_FAILED
    assert report["ok"] is False
    assert report["results"][0]["detail"] == "Invalid data"


def test_a_skip_is_not_a_failure(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "mute_video", _fake_task(SKIPPED, "output already exists"))

    code, report = _json(capsys, "mute", str(clip))

    assert code == cli.EXIT_OK
    assert report["counts"] == {"ok": 0, "skipped": 1, "failed": 0, "over": 0}


def test_a_skip_is_not_drawn_as_if_something_was_made(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "mute_video", _fake_task(SKIPPED, "it has no sound to remove"))

    _, out, _ = _run(capsys, "mute", str(clip))

    assert out.startswith("skipped")
    assert "->" not in out
    assert "no sound" in out


def test_plain_output_is_one_line_per_file(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "mute_video", _fake_task())

    code, out, _ = _run(capsys, "mute", str(clip))

    assert code == cli.EXIT_OK
    assert "ok" in out and "clip-out.mov" in out


# --- where things go -------------------------------------------------------

def test_output_goes_to_a_converted_folder_beside_the_source_by_default(capsys, monkeypatch, clip):
    task = _fake_task()
    monkeypatch.setattr(cli, "mute_video", task)

    _run(capsys, "mute", str(clip))

    assert task.calls[0]["dest_dir"] == clip.parent / "converted"


def test_out_chooses_the_folder(capsys, monkeypatch, clip, tmp_path):
    task = _fake_task()
    monkeypatch.setattr(cli, "mute_video", task)

    _run(capsys, "mute", str(clip), "--out", str(tmp_path / "elsewhere"))

    assert task.calls[0]["dest_dir"] == tmp_path / "elsewhere"


def test_overwrite_is_off_unless_asked(capsys, monkeypatch, clip):
    task = _fake_task()
    monkeypatch.setattr(cli, "mute_video", task)

    _run(capsys, "mute", str(clip))
    _run(capsys, "mute", str(clip), "--overwrite")

    assert [call["overwrite"] for call in task.calls] == [False, True]


# --- each operation gets its settings --------------------------------------

def test_convert_passes_the_target(capsys, monkeypatch, clip):
    task = _fake_task()
    monkeypatch.setattr(cli, "convert_video", task)
    monkeypatch.setattr(cli, "probe_media", lambda p: _info(p))

    _run(capsys, "convert", str(clip), "--to", "mp4")

    assert task.calls[0]["args"] == ("mp4",)
    assert task.calls[0]["force_video_encode"] is False


def test_convert_re_encodes_video_apple_cannot_play_unless_told_not_to(capsys, monkeypatch, clip):
    task = _fake_task()
    monkeypatch.setattr(cli, "convert_video", task)
    monkeypatch.setattr(cli, "probe_media", lambda p: _info(p, video_codec="av1"))

    _run(capsys, "convert", str(clip), "--to", "mp4")
    _run(capsys, "convert", str(clip), "--to", "mp4", "--keep-codec")

    assert [call["force_video_encode"] for call in task.calls] == [True, False]


def test_convert_refuses_a_format_it_does_not_offer(capsys, clip):
    code, _, err = _run(capsys, "convert", str(clip), "--to", "gif")

    assert code == cli.EXIT_USAGE
    assert "gif" in err


def test_compress_passes_the_size(capsys, monkeypatch, clip):
    task = _fake_task()
    monkeypatch.setattr(cli, "compress_video", task)

    _run(capsys, "compress", str(clip), "--size", "8MB")

    assert task.calls[0]["target_bytes"] == 8 * 1024 * 1024


def test_trim_passes_the_range_and_a_fast_cut_by_default(capsys, monkeypatch, clip):
    task = _fake_task()
    monkeypatch.setattr(cli, "trim_video", task)

    _run(capsys, "trim", str(clip), "--start", "0:10", "--end", "1:30")
    _run(capsys, "trim", str(clip), "--start", "10", "--exact")

    first, second = task.calls
    assert (first["start"], first["end"], first["precise"]) == (10.0, 90.0, False)
    assert (second["start"], second["end"], second["precise"]) == (10.0, None, True)


def test_a_time_that_cannot_be_read_is_a_usage_error(capsys, clip):
    code, _, err = _run(capsys, "trim", str(clip), "--start", "soon")

    assert code == cli.EXIT_USAGE
    assert "soon" in err


def test_help_succeeds(capsys):
    code, out, _ = _run(capsys, "--help")

    assert code == cli.EXIT_OK
    assert "--json" in out


# --- folders ---------------------------------------------------------------

@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "clips"
    for name in ("a.mov", "b.mov", "quiet.mov", "inner/c.mov"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
    return root


def _probe_with_one_silent(path):
    return _info(path, audio_codec=None if path.name == "quiet.mov" else "aac")


def test_a_folder_is_muted_in_one_go(capsys, monkeypatch, folder):
    task = _fake_task()
    monkeypatch.setattr(cli, "mute_video", task)
    monkeypatch.setattr(cli, "probe_media", _probe_with_one_silent)

    code, report = _json(capsys, "mute", str(folder))

    assert code == cli.EXIT_OK
    assert sorted(call["src"].name for call in task.calls) == ["a.mov", "b.mov"]
    assert report["counts"] == {"ok": 2, "skipped": 1, "failed": 0, "over": 0}
    skipped = next(row for row in report["results"] if row["status"] == SKIPPED)
    assert skipped["source"].endswith("quiet.mov")
    assert "no sound" in skipped["detail"]


def test_subfolders_are_included_only_when_asked(capsys, monkeypatch, folder):
    task = _fake_task()
    monkeypatch.setattr(cli, "mute_video", task)
    monkeypatch.setattr(cli, "probe_media", _probe_with_one_silent)

    _run(capsys, "mute", str(folder), "--recursive")

    deep = next(call for call in task.calls if call["src"].name == "c.mov")
    assert deep["dest_dir"] == folder / "converted" / "inner"


def test_a_folder_is_converted_in_one_go(capsys, monkeypatch, folder):
    task = _fake_task()
    monkeypatch.setattr(cli, "convert_video", task)
    monkeypatch.setattr(cli, "probe_media", lambda p: _info(p))

    code, report = _json(capsys, "convert", str(folder), "--to", "mp4")

    assert code == cli.EXIT_OK
    assert len(task.calls) == 3
    assert all(call["args"] == ("mp4",) for call in task.calls)


# --- links -----------------------------------------------------------------

def _fake_download(path: Path):
    calls = []

    def fetch(url, dest_dir, **kwargs):
        calls.append({"url": url, "dest_dir": Path(dest_dir), **kwargs})
        return DownloadResult(url=url, status=OK, title="A video", path=path, size_bytes=1234)

    fetch.calls = calls
    return fetch


def test_download_caps_the_quality_it_is_given(capsys, monkeypatch, tmp_path):
    fetch = _fake_download(tmp_path / "A video.mp4")
    monkeypatch.setattr(cli, "download", fetch)

    _run(capsys, "download", "https://youtu.be/9cwf3BGhqFA", "--quality", "720")
    _run(capsys, "download", "https://youtu.be/9cwf3BGhqFA")

    assert [call["max_height"] for call in fetch.calls] == [720, None]


def test_download_tidies_the_link_first(capsys, monkeypatch, tmp_path):
    fetch = _fake_download(tmp_path / "A video.mp4")
    monkeypatch.setattr(cli, "download", fetch)

    _run(capsys, "download",
         "https://www.youtube.com/watch?v=9cwf3BGhqFA&list=RD9cwf3BGhqFA&start_radio=1")

    assert "list=" not in fetch.calls[0]["url"]


def test_download_saves_into_the_current_folder_by_default(capsys, monkeypatch, tmp_path):
    fetch = _fake_download(tmp_path / "A video.mp4")
    monkeypatch.setattr(cli, "download", fetch)
    monkeypatch.chdir(tmp_path)

    code, report = _json(capsys, "download", "https://youtu.be/9cwf3BGhqFA")

    assert code == cli.EXIT_OK
    assert fetch.calls[0]["dest_dir"] == tmp_path
    assert report["results"][0]["output"] == str(tmp_path / "A video.mp4")


def test_audio_converts_to_mp3_unless_told_not_to(capsys, monkeypatch, tmp_path):
    fetch = _fake_download(tmp_path / "A video.mp3")
    monkeypatch.setattr(cli, "download", fetch)

    _run(capsys, "audio", "https://youtu.be/9cwf3BGhqFA")
    _run(capsys, "audio", "https://youtu.be/9cwf3BGhqFA", "--no-mp3")

    assert [call["convert_to"] for call in fetch.calls] == ["mp3", None]
    assert all(call["mode"] == "audio" for call in fetch.calls)


def test_a_link_that_is_not_a_link_is_a_usage_error(capsys):
    code, _, err = _run(capsys, "download", "not a link at all")

    assert code == cli.EXIT_USAGE
    assert err


def test_formats_lists_what_a_link_offers(capsys, monkeypatch):
    monkeypatch.setattr(cli, "probe", lambda url: VideoInfo(
        url=url, title="A video", uploader="Someone", duration=61.0, entries=1,
        formats=[{"format_id": "22", "ext": "mp4", "height": 720, "vcodec": "avc1",
                  "acodec": "mp4a"}],
    ))

    code, report = _json(capsys, "formats", "https://youtu.be/9cwf3BGhqFA")

    assert code == cli.EXIT_OK
    assert report["title"] == "A video"
    assert report["formats"][0]["id"] == "22"


def test_a_link_that_cannot_be_read_fails(capsys, monkeypatch):
    monkeypatch.setattr(cli, "probe", lambda url: VideoInfo(url=url, error="HTTP Error 404"))

    code, report = _json(capsys, "formats", "https://youtu.be/9cwf3BGhqFA")

    assert code == cli.EXIT_FAILED
    assert "404" in report["error"]


# --- info ------------------------------------------------------------------

def test_info_describes_a_local_file(capsys, monkeypatch, clip):
    monkeypatch.setattr(cli, "probe_media", lambda p: _info(p, audio_codec=None))

    code, report = _json(capsys, "info", str(clip))

    assert code == cli.EXIT_OK
    assert report["video_codec"] == "h264"
    assert report["audio_codec"] is None
    assert report["path"] == str(clip)


# --- the guide for agents stays true ----------------------------------------

def test_every_command_is_in_the_agent_guide():
    guide = (Path(__file__).resolve().parent.parent / "docs" / "agents.md").read_text()

    for command in cli.COMMANDS:
        assert f"vidkit {command}" in guide, f"docs/agents.md never shows vidkit {command}"
