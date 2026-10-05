from pathlib import Path

import pytest

from video_toolkit.batch import (
    BatchItem,
    BatchResult,
    estimated_seconds,
    find_videos,
    mirrored_dest,
    plan_batch,
    run_batch,
)
from video_toolkit.media import MediaInfo
from video_toolkit.operations import FAILED, OK, SKIPPED, EncodeResult


def _info(path, **over):
    base = dict(
        path=Path(path), size_bytes=1000, duration=60.0, width=1920, height=1080,
        video_codec="h264", audio_codec="aac",
    )
    base.update(over)
    return MediaInfo(**base)


# --- finding the videos ----------------------------------------------------

def test_only_videos_are_picked_up(touch, tmp_path):
    touch("a.mov")
    touch("b.MP4")
    touch("notes.txt")
    touch("photo.jpg")

    assert [p.name for p in find_videos(tmp_path)] == ["a.mov", "b.MP4"]


def test_subfolders_are_left_alone_unless_asked(touch, tmp_path):
    touch("top.mov")
    touch("inner/deep.mov")

    assert [p.name for p in find_videos(tmp_path)] == ["top.mov"]
    assert [p.name for p in find_videos(tmp_path, recursive=True)] == ["deep.mov", "top.mov"]


def test_the_output_folder_is_not_scanned(touch, tmp_path):
    """Otherwise a second run converts the first run's results."""
    touch("clip.mov")
    touch("converted/clip.mp4")

    found = find_videos(tmp_path, recursive=True, exclude=[tmp_path / "converted"])

    assert [p.name for p in found] == ["clip.mov"]


@pytest.mark.parametrize("dest", [".", ".."])
def test_saving_beside_the_originals_does_not_hide_them(touch, tmp_path, dest):
    touch("videos/clip.mov")
    root = tmp_path / "videos"

    found = find_videos(root, recursive=True, exclude=[root / dest])

    assert [p.name for p in found] == ["clip.mov"]


def test_hidden_files_are_ignored(touch, tmp_path):
    """macOS leaves ._clip.mov beside every file copied to an external drive."""
    touch("clip.mov")
    touch("._clip.mov")

    assert [p.name for p in find_videos(tmp_path)] == ["clip.mov"]


def test_a_missing_folder_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_videos(tmp_path / "nope")


# --- where each one goes ---------------------------------------------------

def test_a_top_level_file_goes_straight_into_the_output_folder(tmp_path):
    assert mirrored_dest(tmp_path / "a.mov", tmp_path, tmp_path / "out") == tmp_path / "out"


def test_a_nested_file_keeps_its_subfolder(tmp_path):
    """Mirroring the tree is what stops a/clip.mov and b/clip.mov colliding."""
    src = tmp_path / "trip" / "day1" / "a.mov"

    assert mirrored_dest(src, tmp_path, tmp_path / "out") == tmp_path / "out" / "trip" / "day1"


# --- deciding what to do with each ----------------------------------------

def test_every_readable_video_becomes_an_item(tmp_path):
    infos = [_info(tmp_path / "a.mov"), _info(tmp_path / "b.mkv")]

    items, settled = plan_batch(infos, tmp_path, tmp_path / "out", "mp4")

    assert [i.info.path.name for i in items] == ["a.mov", "b.mkv"]
    assert settled == []


def test_an_unreadable_file_fails_without_stopping_the_rest(tmp_path):
    infos = [_info(tmp_path / "bad.mov", error="moov atom not found"), _info(tmp_path / "ok.mov")]

    items, settled = plan_batch(infos, tmp_path, tmp_path / "out", "mp4")

    assert [i.info.path.name for i in items] == ["ok.mov"]
    assert settled[0].status == FAILED
    assert "moov atom" in settled[0].detail


def test_a_file_already_in_the_format_is_skipped(tmp_path):
    """Copying an mp4 into an mp4 only duplicates it."""
    items, settled = plan_batch([_info(tmp_path / "a.MP4")], tmp_path, tmp_path / "out", "mp4")

    assert items == []
    assert settled[0].status == SKIPPED
    assert "already mp4" in settled[0].detail


def test_a_file_already_in_the_format_is_kept_when_it_will_be_re_encoded(tmp_path):
    """An AV1 mp4 re-encoded so it plays is real work, not a duplicate."""
    infos = [_info(tmp_path / "a.mp4", video_codec="av1")]

    items, settled = plan_batch(infos, tmp_path, tmp_path / "out", "mp4", force_awkward=True)

    assert [i.info.path.name for i in items] == ["a.mp4"]
    assert items[0].force_video_encode


def test_re_encoding_for_playback_only_touches_files_that_need_it(tmp_path):
    """Forcing every file would re-encode H.264 that plays perfectly well."""
    infos = [_info(tmp_path / "a.mkv", video_codec="av1"), _info(tmp_path / "b.mkv")]

    items, _ = plan_batch(infos, tmp_path, tmp_path / "out", "mp4", force_awkward=True)

    assert {i.info.path.name: i.force_video_encode for i in items} == {"a.mkv": True, "b.mkv": False}


def test_two_files_that_would_share_an_output_are_not_both_converted(tmp_path):
    infos = [_info(tmp_path / "clip.mkv"), _info(tmp_path / "clip.mov")]

    items, settled = plan_batch(infos, tmp_path, tmp_path / "out", "mp4")

    assert [i.info.path.name for i in items] == ["clip.mkv"]
    assert settled[0].status == SKIPPED
    assert "clip.mp4" in settled[0].detail


def test_a_file_converted_by_an_earlier_run_is_not_counted_again(tmp_path, touch):
    """The question before starting should give the number that will really run."""
    touch("out/clip.mp4")

    items, settled = plan_batch([_info(tmp_path / "clip.mkv")], tmp_path, tmp_path / "out", "mp4")

    assert items == []
    assert settled[0].status == SKIPPED
    assert "already in the output folder" in settled[0].detail


def test_same_names_in_different_subfolders_do_not_clash(tmp_path):
    infos = [_info(tmp_path / "a" / "clip.mkv"), _info(tmp_path / "b" / "clip.mkv")]

    items, settled = plan_batch(infos, tmp_path, tmp_path / "out", "mp4")

    assert [i.dest_dir for i in items] == [tmp_path / "out" / "a", tmp_path / "out" / "b"]
    assert settled == []


def test_a_repackage_is_estimated_as_near_instant(tmp_path):
    items, _ = plan_batch([_info(tmp_path / "a.mkv")], tmp_path, tmp_path / "out", "mp4")

    assert items[0].lossless
    assert estimated_seconds(items) == pytest.approx(1.0)


def test_re_encodes_add_up(tmp_path):
    infos = [_info(tmp_path / "a.mkv", video_codec="vp9"), _info(tmp_path / "b.mkv", video_codec="vp9")]

    items, _ = plan_batch(infos, tmp_path, tmp_path / "out", "mp4")

    assert not items[0].lossless
    assert estimated_seconds(items) == pytest.approx(2 * items[0].estimate)


def test_one_unknown_length_makes_the_whole_wait_unknown(tmp_path):
    infos = [_info(tmp_path / "a.mkv", video_codec="vp9", duration=None), _info(tmp_path / "b.mkv")]

    items, _ = plan_batch(infos, tmp_path, tmp_path / "out", "mp4")

    assert estimated_seconds(items) is None


# --- running them ----------------------------------------------------------

def _item(tmp_path, name, estimate=1.0):
    return BatchItem(info=_info(tmp_path / name), dest_dir=tmp_path / "out",
                     lossless=False, estimate=estimate)


def _ok(item, report):
    report(50.0)
    report(100.0)
    return EncodeResult(item.info.path, item.dest_dir / item.info.path.name, OK, 10, 5)


def test_every_item_is_converted_in_order(tmp_path):
    items = [_item(tmp_path, "a.mkv"), _item(tmp_path, "b.mkv")]

    results = run_batch(items, _ok)

    assert [r.source.name for r in results] == ["a.mkv", "b.mkv"]
    assert all(r.status == OK for r in results)


def test_progress_covers_the_whole_batch_not_each_file(tmp_path):
    """A bar that refills for every file says nothing about how long is left."""
    items = [_item(tmp_path, "a.mkv", estimate=3.0), _item(tmp_path, "b.mkv", estimate=1.0)]
    seen = []

    run_batch(items, _ok, seen.append)

    assert seen == sorted(seen)
    assert seen[0] == pytest.approx(37.5)   # halfway through three quarters of the work
    assert seen[-1] == pytest.approx(100.0)


def test_a_file_that_blows_up_does_not_end_the_batch(tmp_path):
    items = [_item(tmp_path, "a.mkv"), _item(tmp_path, "b.mkv")]

    def convert(item, report):
        if item.info.path.name == "a.mkv":
            raise OSError("disk full")
        return _ok(item, report)

    results = run_batch(items, convert)

    assert results[0].status == FAILED
    assert "disk full" in results[0].detail
    assert results[1].status == OK


def test_the_batch_result_counts_each_outcome(tmp_path):
    results = [
        EncodeResult(tmp_path / "a", tmp_path / "a.mp4", OK, 100, 40),
        EncodeResult(tmp_path / "b", tmp_path / "b.mp4", OK, 100, 60),
        EncodeResult(tmp_path / "c", None, SKIPPED, 100, 0, "already mp4"),
        EncodeResult(tmp_path / "d", None, FAILED, 100, 0, "boom"),
    ]

    batch = BatchResult(results, tmp_path / "out")

    assert len(batch.of_status(OK)) == 2
    assert len(batch.of_status(SKIPPED)) == 1
    assert len(batch.of_status(FAILED)) == 1
    assert (batch.source_bytes, batch.output_bytes) == (200, 100)
    assert batch.output == tmp_path / "out"
