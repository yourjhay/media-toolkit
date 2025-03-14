import pytest

from video_toolkit.formats import (
    NO_FFMPEG_CEILING,
    describe_format,
    format_selector,
    quality_warning,
    readable_formats,
)


def test_with_ffmpeg_video_and_audio_streams_are_merged():
    """The `+` is what asks yt-dlp to mux two streams; it needs ffmpeg."""
    selector = format_selector(mode="video", ffmpeg=True)

    assert "+" in selector


def test_without_ffmpeg_only_pre_muxed_formats_are_requested():
    """Asking to merge without a merger produces a download that cannot finish."""
    selector = format_selector(mode="video", ffmpeg=False)

    assert "+" not in selector


def test_a_height_limit_reaches_the_selector():
    assert "720" in format_selector(mode="video", ffmpeg=True, max_height=720)
    assert "720" in format_selector(mode="video", ffmpeg=False, max_height=720)


def test_no_height_limit_leaves_the_selector_unconstrained():
    assert "height" not in format_selector(mode="video", ffmpeg=True)


def test_audio_mode_asks_for_audio():
    assert "bestaudio" in format_selector(mode="audio", ffmpeg=True)


def test_audio_without_ffmpeg_prefers_a_container_that_needs_no_conversion():
    selector = format_selector(mode="audio", ffmpeg=False)

    assert "m4a" in selector


def test_an_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        format_selector(mode="hologram", ffmpeg=True)


def test_the_warning_explains_the_ceiling_and_how_to_lift_it():
    warning = quality_warning(ffmpeg=False)

    assert warning is not None
    assert str(NO_FFMPEG_CEILING) in warning
    assert "brew install ffmpeg" in warning


def test_no_warning_when_ffmpeg_is_present():
    assert quality_warning(ffmpeg=True) is None


def test_a_format_row_reads_as_a_person_would_describe_it():
    row = describe_format(
        {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 30,
         "filesize": 1024 * 1024 * 50, "vcodec": "avc1", "acodec": "none"}
    )

    assert row["id"] == "137"
    assert row["resolution"] == "1080p"
    assert row["ext"] == "mp4"
    assert "50.0 MB" in row["size"]
    assert row["kind"] == "video only"


def test_an_audio_only_format_is_labelled_as_such():
    row = describe_format({"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a"})

    assert row["kind"] == "audio only"
    assert row["resolution"] == "—"


def test_a_complete_format_is_labelled_video_and_audio():
    row = describe_format(
        {"format_id": "18", "ext": "mp4", "height": 360, "vcodec": "avc1", "acodec": "mp4a"}
    )

    assert row["kind"] == "video + audio"


def test_an_unknown_filesize_does_not_invent_one():
    row = describe_format({"format_id": "x", "ext": "mp4", "vcodec": "avc1", "acodec": "none"})

    assert row["size"] == "—"


def test_an_estimated_filesize_is_used_when_the_exact_one_is_missing():
    row = describe_format(
        {"format_id": "x", "ext": "mp4", "filesize_approx": 1024 * 1024, "vcodec": "avc1", "acodec": "none"}
    )

    assert "1.0 MB" in row["size"]


def test_formats_are_listed_best_first():
    info = {"formats": [
        {"format_id": "a", "ext": "mp4", "height": 360, "vcodec": "avc1", "acodec": "mp4a"},
        {"format_id": "b", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none"},
        {"format_id": "c", "ext": "m4a", "vcodec": "none", "acodec": "mp4a"},
    ]}

    rows = readable_formats(info)

    assert [r["id"] for r in rows][0] == "b", "the highest resolution should lead"
    assert len(rows) == 3


def test_listing_formats_of_something_with_none_is_empty():
    assert readable_formats({}) == []
