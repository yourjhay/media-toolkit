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


def test_local_operations_are_marked_as_working_on_files():
    from video_toolkit.planning import LOCAL, OPERATIONS

    assert LOCAL <= set(OPERATIONS)
    assert {"convert", "compress", "trim"} == set(LOCAL)


def test_link_operations_and_file_operations_do_not_overlap():
    from video_toolkit.planning import LOCAL, READ_ONLY

    assert not (LOCAL & READ_ONLY)


def test_every_menu_card_maps_to_an_operation_or_quit():
    from video_toolkit.planning import OPERATIONS, QUIT, menu_items

    for item in menu_items():
        assert item.key in OPERATIONS or item.key == QUIT


def test_every_operation_has_a_card():
    from video_toolkit.planning import OPERATIONS, menu_items

    keys = {item.key for item in menu_items()}
    assert set(OPERATIONS) <= keys


def test_the_size_presets_climb():
    from video_toolkit.planning import SIZE_PRESETS

    sizes = [size for _, size in SIZE_PRESETS]
    assert sizes == sorted(sizes)


def test_the_quality_presets_reach_4k():
    """4K works, but a menu stopping at 1080p implies it does not."""
    from video_toolkit.planning import QUALITY_PRESETS

    heights = [h for _, h in QUALITY_PRESETS if h is not None]
    assert 2160 in heights


def test_the_presets_descend_from_best_to_smallest():
    from video_toolkit.planning import QUALITY_PRESETS

    assert QUALITY_PRESETS[0][1] is None, "best available should lead"
    heights = [h for _, h in QUALITY_PRESETS if h is not None]
    assert heights == sorted(heights, reverse=True)


def test_every_preset_is_labelled_with_its_resolution():
    from video_toolkit.planning import QUALITY_PRESETS

    for label, height in QUALITY_PRESETS:
        if height is not None:
            assert str(height) in label


def test_a_capped_preset_produces_a_capped_selector():
    from video_toolkit.formats import VIDEO, format_selector
    from video_toolkit.planning import QUALITY_PRESETS

    for _, height in QUALITY_PRESETS:
        selector = format_selector(mode=VIDEO, ffmpeg=True, max_height=height)
        if height is None:
            assert "height" not in selector
        else:
            assert str(height) in selector


def test_the_jobs_card_reports_what_is_running():
    from video_toolkit.planning import menu_items

    card = next(item for item in menu_items("2 running") if item.key == "jobs")

    assert card.detail == "2 running"


def test_the_jobs_card_says_so_when_nothing_is_running():
    from video_toolkit.planning import menu_items

    card = next(item for item in menu_items() if item.key == "jobs")

    assert "nothing" in card.detail


def test_watching_jobs_writes_nothing():
    from video_toolkit.planning import READ_ONLY

    assert "jobs" in READ_ONLY


def test_the_link_prompt_explains_what_it_takes():
    """Arriving at a bare "Link:" tells you nothing about what it accepts."""
    from video_toolkit.planning import LINK_HELP

    assert "YouTube" in LINK_HELP
    assert "playlist" in LINK_HELP.lower()


def test_the_link_help_points_at_the_read_only_option():
    from video_toolkit.planning import LINK_HELP

    assert "List formats" in LINK_HELP


def test_the_link_help_fits_a_narrow_terminal():
    """Printed as written, so an over-long line would wrap raggedly."""
    from video_toolkit.planning import LINK_HELP

    assert all(len(line) <= 72 for line in LINK_HELP.splitlines())
