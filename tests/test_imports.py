"""Every module must import cleanly.

`tui` is glue and has no unit tests of its own, so without this a typo in its
imports would sail through a fully green suite and only show up when the app
is actually launched. That happened once; this stops it happening again.
"""

import importlib
import pkgutil

import pytest

import image_toolkit

MODULES = sorted(m.name for m in pkgutil.iter_modules(image_toolkit.__path__))


def test_the_package_ships_the_modules_we_expect():
    assert {"banner", "core", "discovery", "estimate", "info", "jobs", "menu",
            "planning", "tui"} <= set(MODULES)


@pytest.mark.parametrize("name", MODULES)
def test_module_imports_cleanly(name):
    importlib.import_module(f"image_toolkit.{name}")


def test_every_name_tui_imports_actually_exists():
    """Catches an import list that drifted from what the modules export."""
    importlib.import_module("image_toolkit.tui")


def test_the_entry_point_is_callable():
    from image_toolkit.tui import main

    assert callable(main)
