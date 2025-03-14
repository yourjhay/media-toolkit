"""The answers you get by pressing Enter.

Defaults are the whole interface for anyone in a hurry, and a flipped one is
the sort of change nobody notices until it has cost them something — a
re-download, or a folder quietly filling with webm files nobody wanted. The
source is parsed rather than the prompts run, so this holds without a terminal.
"""

import ast
import pathlib

import pytest

import video_toolkit.tui

SOURCE = ast.parse(pathlib.Path(video_toolkit.tui.__file__).read_text())


def _confirm_defaults() -> dict[str, bool]:
    """Every questionary.confirm in the video TUI, by its question text."""
    found = {}
    for node in ast.walk(SOURCE):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", None) != "confirm":
            continue

        question = node.args[0] if node.args else None
        if isinstance(question, ast.Constant):
            text = question.value
        elif isinstance(question, ast.JoinedStr):
            text = "".join(
                part.value for part in question.values if isinstance(part, ast.Constant)
            )
        else:
            continue

        default = next(
            (kw.value.value for kw in node.keywords
             if kw.arg == "default" and isinstance(kw.value, ast.Constant)),
            None,
        )
        found[text.strip()] = default
    return found


DEFAULTS = _confirm_defaults()


@pytest.mark.parametrize("question,expected", [
    ("Convert to MP3?", True),
    ("Keep the original file as well?", False),
    ("Download ?", True),
    ("Go ahead?", True),
    ("Fast cut? (instant, but snaps to the nearest keyframe)", True),
])
def test_pressing_enter_gives_the_expected_answer(question, expected):
    assert question in DEFAULTS, f"no confirm asks {question!r}; found {sorted(DEFAULTS)}"
    assert DEFAULTS[question] is expected


def test_every_confirmation_states_its_default():
    """A confirm without one defaults to No, which is rarely what was meant."""
    missing = [q for q, d in DEFAULTS.items() if d is None]

    assert not missing, f"these ask without saying what Enter does: {missing}"
