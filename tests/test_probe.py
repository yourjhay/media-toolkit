import pytest

from image_toolkit.core import probe_quality_sizes


def test_probing_returns_a_size_for_every_requested_quality(make_jpg):
    sizes = probe_quality_sizes(make_jpg("photo.jpg"), "jpg", (20, 60, 90))

    assert set(sizes) == {20, 60, 90}
    assert all(n > 0 for n in sizes.values())


def test_higher_quality_measures_bigger(make_jpg):
    sizes = probe_quality_sizes(make_jpg("photo.jpg", width=800, height=600), "jpg", (20, 60, 95))

    assert sizes[20] < sizes[60] < sizes[95]


def test_a_heic_source_can_be_probed_for_jpeg_output(make_heic):
    sizes = probe_quality_sizes(make_heic("shot.heic"), "jpg", (30, 90))

    assert sizes[30] < sizes[90]


def test_webp_can_be_probed_too(make_png):
    sizes = probe_quality_sizes(make_png("chart.png", width=400, height=300), "webp", (20, 90))

    assert sizes[20] < sizes[90]


def test_probing_measures_what_the_real_conversion_writes(make_jpg, tmp_path):
    """An estimate that does not match the encoder it predicts is worthless."""
    from image_toolkit.core import convert_to_webp

    src = make_jpg("photo.jpg", width=400, height=300)
    probed = probe_quality_sizes(src, "webp", (70,))[70]
    written = convert_to_webp(src, tmp_path / "out", quality=70).output_bytes

    assert probed == written


def test_an_unsupported_probe_format_is_rejected(make_jpg):
    with pytest.raises(ValueError):
        probe_quality_sizes(make_jpg("photo.jpg"), "gif", (50,))
