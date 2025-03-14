import pytest

from image_toolkit.estimate import (
    QUALITY_ANCHORS,
    SizeModel,
    build_quality_model,
    compress_target,
)


def test_anchors_span_the_whole_quality_scale_and_cluster_at_the_top():
    """JPEG size nearly doubles between q95 and q100, so the top needs detail."""
    assert min(QUALITY_ANCHORS) <= 10
    assert max(QUALITY_ANCHORS) == 100
    assert len([q for q in QUALITY_ANCHORS if q >= 85]) >= 3


def test_an_anchor_estimates_to_its_measured_size_exactly():
    model = SizeModel({10: 400, 50: 1100, 100: 6000}, source_bytes=1800)

    assert model.estimate(50) == 1100


def test_between_anchors_it_interpolates():
    model = SizeModel({0: 0, 100: 1000}, source_bytes=1000)

    assert model.estimate(50) == 500
    assert model.estimate(25) == 250


def test_below_the_lowest_anchor_it_clamps_rather_than_extrapolating():
    model = SizeModel({10: 400, 100: 6000}, source_bytes=1800)

    assert model.estimate(1) == 400


def test_above_the_highest_anchor_it_clamps():
    model = SizeModel({10: 400, 90: 2400}, source_bytes=1800)

    assert model.estimate(100) == 2400


def test_estimates_rise_with_quality():
    model = SizeModel({10: 400, 30: 790, 95: 3200, 100: 5900}, source_bytes=1800)
    sizes = [model.estimate(q) for q in range(1, 101)]

    assert sizes == sorted(sizes)


def test_a_single_anchor_answers_the_same_for_every_quality():
    model = SizeModel({50: 900}, source_bytes=1800)

    assert model.estimate(1) == model.estimate(100) == 900


def test_a_model_with_no_anchors_is_rejected():
    with pytest.raises(ValueError):
        SizeModel({}, source_bytes=100)


def test_building_a_model_measures_each_anchor_once():
    calls = []

    def fake_encode(quality):
        calls.append(quality)
        return quality * 10

    model = build_quality_model(fake_encode, source_bytes=1000, anchors=(10, 50, 90))

    assert calls == [10, 50, 90]
    assert model.estimate(50) == 500


def test_a_batch_scales_the_sample_up_by_total_size():
    """One file is measured; the rest of the batch is scaled from its ratio."""
    model = build_quality_model(
        lambda q: 500,
        source_bytes=1000,
        anchors=(50,),
        batch_source_bytes=10_000,
    )

    assert model.estimate(50) == 5000
    assert model.scaled is True


def test_a_single_file_model_is_not_marked_as_scaled():
    model = build_quality_model(lambda q: 500, source_bytes=1000, anchors=(50,))

    assert model.scaled is False


def test_compress_target_is_the_requested_fraction_of_the_source():
    assert compress_target(1000, 60) == 400
    assert compress_target(1_000_000, 50) == 500_000


def test_compress_target_rejects_a_percentage_outside_the_usable_range():
    for bad in (0, 100, -5, 150):
        with pytest.raises(ValueError):
            compress_target(1000, bad)
