"""install.sh, the one-line installer: fetch the toolkit, then hand over to setup.sh.

Run the way people run it, piped into a shell with nothing on the other end of
stdin. Each test clones a throwaway repository standing in for GitHub, whose
setup.sh only records how it was called, so nothing here builds a virtualenv
or installs a package. --no-deps keeps the system package manager out of it.

Every test runs under each POSIX shell present, because `curl | sh` is dash on
Debian and Ubuntu, and a bashism there fails only for those users.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
INSTALL = PROJECT / "install.sh"

SHELLS = [name for name in ("sh", "dash", "bash") if shutil.which(name)]

FAKE_SETUP = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$(dirname "$0")/setup-args"
printf '%s\\n' "${PYTHON:-}" > "$(dirname "$0")/setup-python"
"""


def git(*args, cwd):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


@pytest.fixture
def upstream(tmp_path):
    """A repository shaped like the toolkit, standing in for GitHub."""
    repo = tmp_path / "upstream"
    repo.mkdir()
    (repo / "setup.sh").write_text(FAKE_SETUP)
    (repo / "setup.sh").chmod(0o755)
    for name in ("imgkit", "vidkit"):
        (repo / name).write_text("#!/usr/bin/env bash\n")
    git("init", "-q", "-b", "main", cwd=repo)
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "first", cwd=repo)
    return repo


@pytest.fixture
def home(tmp_path):
    path = tmp_path / "home"
    path.mkdir()
    return path


def install(shell, *args, home, path=None, user_shell="/bin/zsh"):
    return subprocess.run(
        [shell, "-s", "--", *args],
        input=INSTALL.read_text(), capture_output=True, text=True, timeout=120,
        env={**os.environ, "HOME": str(home), "SHELL": user_shell,
             "PATH": path or os.environ["PATH"]},
    )


def fetch(shell, upstream, home, *extra, **kwargs):
    return install(
        shell, "--no-deps", "--repo", str(upstream),
        "--dir", str(home / "toolkit"), "--bin-dir", str(home / "bin"),
        *extra, home=home, **kwargs,
    )


def test_the_script_exists_and_is_executable():
    assert INSTALL.exists()
    assert os.access(INSTALL, os.X_OK)


@pytest.mark.parametrize("shell", SHELLS)
def test_it_parses_as_plain_posix_sh(shell):
    result = subprocess.run([shell, "-n", str(INSTALL)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_help_is_offered(shell, home):
    result = install(shell, "--help", home=home)

    assert result.returncode == 0
    assert "--no-deps" in result.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unknown_flag_is_rejected_rather_than_ignored(shell, home):
    result = install(shell, "--flibble", home=home)

    assert result.returncode == 2


@pytest.mark.parametrize("shell", SHELLS)
def test_it_clones_the_toolkit_and_hands_over_to_setup(shell, upstream, home):
    result = fetch(shell, upstream, home, "--no-modify-path")

    assert result.returncode == 0, result.stdout + result.stderr
    args = (home / "toolkit" / "setup-args").read_text().split()
    assert args == ["--link", "--bin-dir", str(home / "bin")]


@pytest.mark.parametrize("shell", SHELLS)
def test_setup_is_given_a_python_new_enough_to_use(shell, upstream, home):
    fetch(shell, upstream, home, "--no-modify-path")

    python = (home / "toolkit" / "setup-python").read_text().strip()
    version = subprocess.run(
        [python, "-c", "import sys; print(sys.version_info >= (3, 10))"],
        capture_output=True, text=True,
    )
    assert version.stdout.strip() == "True"


@pytest.mark.parametrize("shell", SHELLS)
def test_running_it_again_updates_the_copy_it_made(shell, upstream, home):
    """The same one-liner is how people update."""
    fetch(shell, upstream, home, "--no-modify-path")
    (upstream / "NEW").write_text("new\n")
    git("add", "NEW", cwd=upstream)
    git("commit", "-q", "-m", "second", cwd=upstream)

    result = fetch(shell, upstream, home, "--no-modify-path")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / "toolkit" / "NEW").exists()


@pytest.mark.parametrize("shell", SHELLS)
def test_it_will_not_install_over_a_folder_that_is_not_the_toolkit(shell, upstream, home):
    """Whatever is already there is not ours to clone over or delete."""
    target = home / "toolkit"
    target.mkdir()
    (target / "thesis.txt").write_text("five years\n")

    result = fetch(shell, upstream, home, "--no-modify-path")

    assert result.returncode != 0
    assert (target / "thesis.txt").read_text() == "five years\n"
    assert str(target) in result.stdout + result.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_it_puts_the_commands_on_path_in_the_shell_profile(shell, upstream, home):
    result = fetch(shell, upstream, home)

    assert result.returncode == 0, result.stdout + result.stderr
    assert str(home / "bin") in (home / ".zshrc").read_text()


@pytest.mark.parametrize("shell", SHELLS)
def test_the_profile_line_is_added_once_however_often_it_runs(shell, upstream, home):
    fetch(shell, upstream, home)
    fetch(shell, upstream, home)

    assert (home / ".zshrc").read_text().count(str(home / "bin")) == 1


@pytest.mark.parametrize("shell", SHELLS)
def test_bash_users_get_it_in_their_bash_profile(shell, upstream, home):
    fetch(shell, upstream, home, user_shell="/bin/bash")

    written = [p for p in home.iterdir() if p.name.startswith(".bash")]
    assert written, "no bash startup file was written"
    assert all(str(home / "bin") in p.read_text() for p in written)


@pytest.mark.parametrize("shell", SHELLS)
def test_the_profile_is_left_alone_when_the_folder_is_already_on_path(shell, upstream, home):
    fetch(shell, upstream, home, path=f"{home / 'bin'}{os.pathsep}{os.environ['PATH']}")

    assert not (home / ".zshrc").exists()


@pytest.mark.parametrize("shell", SHELLS)
def test_no_modify_path_is_honoured(shell, upstream, home):
    result = fetch(shell, upstream, home, "--no-modify-path")

    assert not (home / ".zshrc").exists()
    assert str(home / "bin") in result.stdout, "it should still say what to add"


@pytest.mark.parametrize("shell", SHELLS)
def test_it_ends_by_saying_where_the_toolkit_lives(shell, upstream, home):
    result = fetch(shell, upstream, home, "--no-modify-path")

    assert str(home / "toolkit") in result.stdout
