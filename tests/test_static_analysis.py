"""Static checks for the mistakes the test suite cannot see.

Importing a module proves its import lines work. It proves nothing about a
name used inside a function that was never imported — that is a NameError at
call time, so the module imports cleanly, every test passes, and the app dies
on launch. That happened: a refactor left `_banner` calling three names that
had moved to another package, and 550 green tests said nothing about it.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
PACKAGES = ["shared", "image_toolkit", "video_toolkit", "tests"]


def _pyflakes() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", *PACKAGES],
        cwd=PROJECT, capture_output=True, text=True, timeout=120,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


REPORT = _pyflakes()


def test_no_module_uses_a_name_it_never_defined():
    """The serious one: this is what crashes the app while tests stay green."""
    undefined = [line for line in REPORT if "undefined name" in line]

    assert not undefined, "\n".join(undefined)


def test_no_module_imports_something_it_does_not_use():
    """Usually harmless, but it is how a half-finished refactor announces itself."""
    unused = [line for line in REPORT if "imported but unused" in line]

    assert not unused, "\n".join(unused)


def test_nothing_else_is_flagged_either():
    assert not REPORT, "\n".join(REPORT)


def test_the_check_would_actually_catch_the_bug_it_exists_for(tmp_path):
    """A guard that cannot fail is not a guard."""
    broken = tmp_path / "broken.py"
    broken.write_text("def go():\n    return was_never_imported(1)\n")

    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", str(broken)],
        capture_output=True, text=True, timeout=60,
    )

    assert "undefined name" in result.stdout


@pytest.mark.parametrize("package", PACKAGES)
def test_every_package_is_actually_being_checked(package):
    assert (PROJECT / package).is_dir()
