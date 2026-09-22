"""questionary substitutes a Choice's title when its value is None.

A None-valued Choice therefore comes back as the label string, quietly
defeating any `is None` check downstream. This has now bitten twice — once on
the main menu's Quit card, once on the metadata reader's "Back to the menu"
entry — so the rule is enforced structurally here rather than per call site.
"""

import ast
import pathlib

import pytest

import image_toolkit

PACKAGE = pathlib.Path(image_toolkit.__file__).parent
SOURCES = sorted(PACKAGE.glob("*.py"))


def _choice_calls_with_none(path: pathlib.Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name != "Choice":
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value is None:
            yield node.lineno
        for keyword in node.keywords:
            if (
                keyword.arg == "value"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is None
            ):
                yield node.lineno


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_choice_is_ever_given_a_none_value(path):
    offenders = list(_choice_calls_with_none(path))

    assert not offenders, (
        f"{path.name} builds a Choice with value=None at line(s) "
        f"{offenders}; use a sentinel string instead, or questionary will "
        f"hand back the label text."
    )


def test_the_guard_actually_detects_the_mistake(tmp_path):
    """A test that cannot fail proves nothing, so prove it catches the bug."""
    bad = tmp_path / "bad.py"
    bad.write_text('Choice("Back to the menu", None)\n')

    assert list(_choice_calls_with_none(bad)) == [1]


def test_the_guard_accepts_a_sentinel(tmp_path):
    good = tmp_path / "good.py"
    good.write_text('Choice("Back to the menu", BACK)\n')

    assert list(_choice_calls_with_none(good)) == []


def test_index_zero_is_a_safe_choice_value():
    """Only None triggers the fallback, so the first file in a list is fine."""
    from questionary import Choice

    assert Choice("first", 0).value == 0


def test_the_reader_back_entry_returns_a_sentinel_not_its_label():
    from image_toolkit.metadata import FileMetadata
    from image_toolkit.planning import BACK
    from image_toolkit.tui import _detail_choices

    readings = [
        FileMetadata(path=pathlib.Path("a.jpg"), name="a.jpg", size_bytes=1),
        FileMetadata(path=pathlib.Path("b.jpg"), name="b.jpg", size_bytes=2),
    ]

    choices = _detail_choices(readings)

    assert [c.value for c in choices[:-1]] == [0, 1]
    assert choices[-1].value == BACK
    assert choices[-1].value != choices[-1].title


# --- the same trap, arriving by a different route ---------------------------

def _preset_tables():
    """Every module-level table that gets turned into Choices."""
    import importlib
    import pkgutil

    found = {}
    for package in ("shared", "image_toolkit", "video_toolkit"):
        root = importlib.import_module(package)
        for info in pkgutil.iter_modules(root.__path__):
            module = importlib.import_module(f"{package}.{info.name}")
            for name in dir(module):
                if name.endswith(("PRESETS", "SCALES")) and not name.startswith("_"):
                    found[f"{package}.{info.name}.{name}"] = getattr(module, name)
    return found


def test_the_preset_tables_are_actually_being_found():
    """A guard that inspects nothing would pass for the wrong reason."""
    names = _preset_tables()

    assert len(names) >= 4, f"expected several preset tables, found {sorted(names)}"


def test_no_preset_table_contains_a_none():
    """The AST guard only sees a literal None written inside Choice(...).

    QUALITY_PRESETS held ("Best available", None) and fed it to Choice through
    a loop variable, so the literal never appeared at the call site and the
    scan saw nothing. The value came back as the label and was spliced into a
    format selector as height<=?Bestavailable. Checking the data itself catches
    it however it reaches the Choice.
    """
    offenders = [
        f"{name}[{index}]"
        for name, table in _preset_tables().items()
        for index, row in enumerate(table)
        if None in (row if isinstance(row, (tuple, list)) else (row,))
    ]

    assert not offenders, (
        f"these presets hold a None, which questionary replaces with the "
        f"label: {offenders}. Use a sentinel instead."
    )


def test_the_check_would_catch_the_bug_it_exists_for():
    """Proved against the exact shape that shipped, rather than assumed."""
    broken = {"somewhere.QUALITY_PRESETS": (("Best available", None), ("Up to 1080p", 1080))}

    offenders = [
        f"{name}[{index}]"
        for name, table in broken.items()
        for index, row in enumerate(table)
        if None in (row if isinstance(row, (tuple, list)) else (row,))
    ]

    assert offenders == ["somewhere.QUALITY_PRESETS[0]"]
