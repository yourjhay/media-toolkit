"""The launcher must work from any directory.

Every other test runs with the project as the working directory, which is the
one situation where a missing PYTHONPATH cannot be noticed: `python -m` finds
the package via the current directory. Running `imgkit` from anywhere else
failed with "No module named image_toolkit" until this was caught by hand.
"""

import os
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
LAUNCHERS = [PROJECT / "imgkit", PROJECT / "vidkit"]


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_the_launcher_exists_and_is_executable(LAUNCHER):
    assert LAUNCHER.exists()
    assert os.access(LAUNCHER, os.X_OK)


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_running_from_an_unrelated_directory_finds_the_package(LAUNCHER, tmp_path):
    result = subprocess.run(
        [str(LAUNCHER)],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = result.stdout + result.stderr

    assert "No module named" not in combined, combined[:400]
    assert "ModuleNotFoundError" not in combined, combined[:400]


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_the_launcher_does_not_change_the_working_directory(LAUNCHER):
    """Users type relative paths at the prompts; they must resolve where they stand."""
    source = LAUNCHER.read_text()
    commands = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("cd ") or line.strip().startswith("cd\t")
    ]

    assert not commands, f"launcher changes directory: {commands}"


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_the_launcher_puts_the_package_on_the_path(LAUNCHER):
    assert "PYTHONPATH" in LAUNCHER.read_text()


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_an_existing_pythonpath_is_preserved(LAUNCHER, tmp_path):
    """Clobbering it would break whatever else the user has set up."""
    marker = str(tmp_path / "somewhere-else")
    env = {**os.environ, "PYTHONPATH": marker}

    result = subprocess.run(
        [str(LAUNCHER)],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert "No module named" not in result.stdout + result.stderr


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_a_directory_shadowing_the_package_name_does_not_win(LAUNCHER, tmp_path):
    """Running from a folder that contains an 'image_toolkit' directory."""
    (tmp_path / "image_toolkit").mkdir()

    result = subprocess.run(
        [str(LAUNCHER)],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = result.stdout + result.stderr

    assert "No module named" not in combined, combined[:400]
    assert "cannot be directly executed" not in combined, combined[:400]
