import pytest

from image_toolkit.sizing import target_size


def test_a_percentage_scales_both_sides():
    assert target_size((4000, 3000), percent=50) == (2000, 1500)


def test_a_percentage_of_one_hundred_changes_nothing():
    assert target_size((4032, 3024), percent=100) == (4032, 3024)


def test_it_refuses_to_upscale_past_the_original():
    """Enlarging invents detail that was never there."""
    assert target_size((800, 600), percent=200) == (800, 600)


def test_a_width_limit_scales_the_height_to_match():
    assert target_size((4032, 3024), max_width=1920) == (1920, 1440)


def test_a_height_limit_scales_the_width_to_match():
    assert target_size((4032, 3024), max_height=1008) == (1344, 1008)


def test_both_limits_fit_inside_the_box():
    width, height = target_size((4032, 3024), max_width=1920, max_height=1000)

    assert width <= 1920 and height <= 1000
    assert height == 1000, "the tighter limit should be the binding one"


def test_a_box_bigger_than_the_image_leaves_it_alone():
    assert target_size((800, 600), max_width=4000, max_height=4000) == (800, 600)


def test_a_portrait_image_keeps_its_aspect_ratio():
    width, height = target_size((3024, 4032), max_width=1000, max_height=1000)

    assert (width, height) == (750, 1000)


def test_aspect_ratio_survives_within_a_pixel():
    original = (1999, 1001)
    width, height = target_size(original, max_width=500)

    assert abs(width / height - original[0] / original[1]) < 0.01


def test_nothing_ever_collapses_to_zero_pixels():
    assert target_size((4000, 3000), percent=1) == (40, 30)
    assert target_size((10, 4), percent=1) == (1, 1)


def test_asking_for_nothing_is_rejected():
    with pytest.raises(ValueError):
        target_size((800, 600))


def test_mixing_a_percentage_with_a_box_is_rejected():
    """Two different answers to the same question; make the caller pick one."""
    with pytest.raises(ValueError):
        target_size((800, 600), percent=50, max_width=400)


def test_a_percentage_outside_the_usable_range_is_rejected():
    for bad in (0, -10):
        with pytest.raises(ValueError):
            target_size((800, 600), percent=bad)


def test_a_limit_of_zero_or_less_is_rejected():
    for bad in (0, -100):
        with pytest.raises(ValueError):
            target_size((800, 600), max_width=bad)
