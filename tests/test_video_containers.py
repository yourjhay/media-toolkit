import pytest

from video_toolkit.containers import (
    CONTAINERS,
    COPY,
    ENCODE,
    plan_conversion,
    supported_targets,
)


def test_a_matching_container_just_repackages():
    """h264 and aac are already legal in mkv, so nothing needs re-encoding."""
    plan = plan_conversion("h264", "aac", "mkv")

    assert (plan.video, plan.audio) == (COPY, COPY)
    assert plan.lossless


def test_only_the_offending_stream_is_re_encoded():
    """opus cannot go in mp4, but the h264 video can be carried across intact."""
    plan = plan_conversion("h264", "opus", "mp4")

    assert plan.video == COPY
    assert plan.audio == ENCODE
    assert plan.audio_encoder == "aac"
    assert not plan.lossless
    assert plan.video_lossless


def test_a_container_that_takes_neither_re_encodes_both():
    plan = plan_conversion("h264", "aac", "webm")

    assert (plan.video, plan.audio) == (ENCODE, ENCODE)
    assert not plan.video_lossless


def test_webm_native_codecs_repackage_into_webm():
    plan = plan_conversion("vp9", "opus", "webm")

    assert plan.lossless


def test_vp9_cannot_be_carried_into_mp4():
    plan = plan_conversion("vp9", "opus", "mp4")

    assert plan.video == ENCODE
    assert plan.video_encoder in ("libx264", "h264_videotoolbox")


def test_hardware_encoding_is_used_when_offered():
    slow = plan_conversion("vp9", "opus", "mp4", hardware=False)
    fast = plan_conversion("vp9", "opus", "mp4", hardware=True)

    assert slow.video_encoder == "libx264"
    assert fast.video_encoder == "h264_videotoolbox"


def test_hardware_encoding_is_ignored_where_it_does_not_apply():
    """There is no hardware VP9 encoder here, so webm must stay on software."""
    plan = plan_conversion("h264", "aac", "webm", hardware=True)

    assert "videotoolbox" not in plan.video_encoder


def test_a_file_with_no_audio_is_handled():
    plan = plan_conversion("h264", None, "mp4")

    assert plan.video == COPY
    assert plan.audio is None
    assert plan.lossless


def test_an_unknown_codec_is_treated_as_incompatible():
    """Better to re-encode something we cannot vouch for than to write a broken file."""
    plan = plan_conversion("some_new_codec", "aac", "mp4")

    assert plan.video == ENCODE


def test_the_reason_explains_the_decision():
    assert "opus" in plan_conversion("h264", "opus", "mp4").reason.lower()
    assert plan_conversion("h264", "aac", "mkv").reason


def test_an_unsupported_target_container_is_rejected():
    with pytest.raises(ValueError):
        plan_conversion("h264", "aac", "avi")


def test_the_target_extension_may_be_written_with_a_dot():
    assert plan_conversion("h264", "aac", ".mkv").lossless


@pytest.mark.parametrize("container", sorted(CONTAINERS))
def test_every_container_declares_what_to_encode_to(container):
    spec = CONTAINERS[container]

    assert spec["default_video"] in spec["video"]
    assert spec["default_audio"] in spec["audio"]


def test_the_offered_targets_are_the_ones_we_know():
    assert set(supported_targets()) == set(CONTAINERS)


# --- legal in the container, but will it play? ------------------------------

def test_av1_in_mp4_is_flagged_even_though_it_is_allowed():
    """Legal in the container is not the same question as plays on your machine."""
    from video_toolkit.containers import playback_warning

    warning = playback_warning("av1", "mp4")

    assert warning is not None
    assert "av1" in warning.lower()


def test_only_a_copyable_codec_is_flagged():
    """The warning is about a choice. Where there is no choice there is no warning.

    mp4 accepts av1, so it can be copied and the question is real. mov accepts
    none of the web codecs, so they are re-encoded regardless and saying
    anything would just be noise.
    """
    from video_toolkit.containers import playback_warning

    assert playback_warning("av1", "mp4") is not None
    for codec in ("av1", "vp9", "vp8"):
        assert playback_warning(codec, "mov") is None
    for codec in ("vp9", "vp8"):
        assert playback_warning(codec, "mp4") is None


def test_h264_and_hevc_raise_no_concern():
    from video_toolkit.containers import playback_warning

    assert playback_warning("h264", "mp4") is None
    assert playback_warning("hevc", "mov") is None


def test_nothing_is_flagged_for_mkv_or_webm():
    """Those are opened with players that handle everything anyway."""
    from video_toolkit.containers import playback_warning

    assert playback_warning("av1", "mkv") is None
    assert playback_warning("vp9", "webm") is None


def test_a_codec_no_container_here_accepts_is_not_flagged():
    from video_toolkit.containers import playback_warning

    assert playback_warning("theora", "mp4") is None


def test_the_warning_names_something_that_does_play_it():
    from video_toolkit.containers import playback_warning

    assert "VLC" in playback_warning("av1", "mp4")


def test_forcing_an_encode_overrides_a_copy():
    plan = plan_conversion("av1", "aac", "mp4", force_video_encode=True)

    assert plan.video == ENCODE
    assert plan.video_encoder in ("libx264", "h264_videotoolbox")
    assert not plan.lossless


def test_forcing_an_encode_leaves_the_audio_decision_alone():
    plan = plan_conversion("av1", "aac", "mp4", force_video_encode=True)

    assert plan.audio == COPY


def test_forcing_says_why_in_the_reason():
    plan = plan_conversion("av1", "aac", "mp4", force_video_encode=True)

    assert "play" in plan.reason.lower()


def test_not_forcing_still_copies_what_it_can():
    plan = plan_conversion("av1", "aac", "mp4")

    assert plan.video == COPY
