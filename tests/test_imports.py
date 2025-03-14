"""Every module in every package must import cleanly.

The TUIs are glue with few unit tests of their own, so without this a typo in
an import list would sail through a fully green suite and only show up when
the app is launched. That has happened twice; this stops it happening again.
"""

import importlib
import pkgutil

import pytest

PACKAGES = ["shared", "image_toolkit", "video_toolkit"]


def _modules(package_name):
    package = importlib.import_module(package_name)
    return [f"{package_name}.{m.name}" for m in pkgutil.iter_modules(package.__path__)]


ALL_MODULES = sorted(name for package in PACKAGES for name in _modules(package))


@pytest.mark.parametrize("name", ALL_MODULES)
def test_module_imports_cleanly(name):
    importlib.import_module(name)


def test_the_shared_package_holds_the_reusable_chrome():
    assert {"shared.banner", "shared.chrome", "shared.format", "shared.menu",
            "shared.paths", "shared.prompts"} <= set(ALL_MODULES)


def test_the_image_package_holds_the_pixel_work():
    assert {"image_toolkit.core", "image_toolkit.discovery", "image_toolkit.estimate",
            "image_toolkit.info", "image_toolkit.jobs", "image_toolkit.metadata",
            "image_toolkit.planning", "image_toolkit.sizing", "image_toolkit.stripper",
            "image_toolkit.tui"} <= set(ALL_MODULES)


def test_the_shared_package_does_not_depend_on_a_toolkit():
    """Shared code importing a toolkit would defeat the point of sharing it."""
    import pathlib

    import shared

    for path in pathlib.Path(shared.__file__).parent.glob("*.py"):
        source = path.read_text()
        for toolkit in ("image_toolkit", "video_toolkit"):
            assert toolkit not in source, f"{path.name} reaches into {toolkit}"


def test_the_video_package_holds_the_download_work():
    assert {"video_toolkit.download", "video_toolkit.formats",
            "video_toolkit.planning", "video_toolkit.tui",
            "video_toolkit.urls"} <= set(ALL_MODULES)


def test_the_two_toolkits_do_not_depend_on_each_other():
    """They share the chrome, not their domains."""
    import pathlib

    import image_toolkit
    import video_toolkit

    for package, forbidden in ((image_toolkit, "video_toolkit"), (video_toolkit, "image_toolkit")):
        for path in pathlib.Path(package.__file__).parent.glob("*.py"):
            assert forbidden not in path.read_text(), f"{path.name} reaches into {forbidden}"


def test_each_entry_point_is_callable():
    from image_toolkit.tui import main as image_main
    from video_toolkit.tui import main as video_main

    assert callable(image_main)
    assert callable(video_main)
