"""setup.sh, including the part that puts the commands on your PATH.

Run as a subprocess, because that is how anyone actually uses it. Every test
passes --link-only so the virtualenv work is skipped; that flag exists for
people who already set up and only want the links, not just for these tests.
"""

import os
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SETUP = PROJECT / "setup.sh"
COMMANDS = ("imgkit", "vidkit")


def run(*args, stdin=subprocess.DEVNULL, env=None):
    return subprocess.run(
        [str(SETUP), *args],
        cwd=PROJECT, stdin=stdin, capture_output=True, text=True, timeout=120,
        env={**os.environ, **(env or {})},
    )


def test_the_script_exists_and_is_executable():
    assert SETUP.exists()
    assert os.access(SETUP, os.X_OK)


def test_it_does_not_hang_when_nothing_can_answer_it(tmp_path):
    """Piped into a shell or run in CI there is no one to press y."""
    result = run("--link-only", "--bin-dir", str(tmp_path))

    assert result.returncode == 0
    assert not (tmp_path / "imgkit").exists(), "it must not link without being asked"


def test_it_says_how_to_link_when_it_could_not_ask(tmp_path):
    result = run("--link-only", "--bin-dir", str(tmp_path))

    assert "--link" in result.stdout


@pytest.mark.parametrize("command", COMMANDS)
def test_linking_creates_a_symlink_to_the_real_launcher(tmp_path, command):
    run("--link-only", "--link", "--bin-dir", str(tmp_path))

    link = tmp_path / command
    assert link.is_symlink()
    assert link.resolve() == (PROJECT / command).resolve()


def test_the_linked_command_actually_runs(tmp_path):
    """A link to the wrong place would still look right in a listing."""
    run("--link-only", "--link", "--bin-dir", str(tmp_path))

    result = subprocess.run(
        [str(tmp_path / "imgkit")], cwd=tmp_path, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=60,
    )

    assert "No module named" not in result.stdout + result.stderr


def test_no_link_is_honoured_even_on_a_terminal(tmp_path):
    result = run("--link-only", "--no-link", "--bin-dir", str(tmp_path))

    assert result.returncode == 0
    assert not (tmp_path / "imgkit").exists()


def test_linking_twice_is_harmless(tmp_path):
    run("--link-only", "--link", "--bin-dir", str(tmp_path))
    result = run("--link-only", "--link", "--bin-dir", str(tmp_path))

    assert result.returncode == 0
    assert (tmp_path / "imgkit").resolve() == (PROJECT / "imgkit").resolve()


def test_it_refuses_to_replace_something_that_is_not_our_link(tmp_path):
    """Whatever else is called imgkit, it is not ours to delete."""
    intruder = tmp_path / "imgkit"
    intruder.write_text("#!/bin/sh\necho something else\n")

    result = run("--link-only", "--link", "--bin-dir", str(tmp_path))

    assert intruder.read_text() == "#!/bin/sh\necho something else\n"
    assert "imgkit" in result.stdout


def test_it_warns_when_the_folder_is_not_on_your_path(tmp_path):
    result = run("--link-only", "--link", "--bin-dir", str(tmp_path), env={"PATH": "/usr/bin:/bin"})

    assert "PATH" in result.stdout


def test_it_stays_quiet_about_path_when_the_folder_is_on_it(tmp_path):
    result = run("--link-only", "--link", "--bin-dir", str(tmp_path),
                 env={"PATH": f"{tmp_path}:/usr/bin:/bin"})

    assert "not on your PATH" not in result.stdout


def test_an_unwritable_target_is_reported_rather_than_crashed_into(tmp_path):
    blocked = tmp_path / "nope"
    blocked.mkdir(mode=0o500)

    result = run("--link-only", "--link", "--bin-dir", str(blocked))

    assert result.returncode != 0
    assert "writ" in result.stdout.lower() + result.stderr.lower()


def test_an_unknown_flag_is_rejected_rather_than_ignored(tmp_path):
    result = run("--link-only", "--flibble", "--bin-dir", str(tmp_path))

    assert result.returncode != 0
