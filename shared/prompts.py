"""Question-asking that any toolkit in this repo can reuse.

No colours, layout or wording specific to images or video: those belong to
whichever toolkit is asking.
"""

from __future__ import annotations

from pathlib import Path

import questionary
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import FormattedText

from .paths import clean_path_input

STYLE = questionary.Style(
    [
        ("qmark", "fg:#00b894 bold"),
        ("question", "bold"),
        ("answer", "fg:#0984e3 bold"),
        ("pointer", "fg:#00b894 bold"),
        ("highlighted", "fg:#00b894 bold"),
        ("selected", "fg:#00b894"),
    ]
)


class Cancelled(Exception):
    """The user pressed Ctrl-C or Esc at a prompt."""


def ask(question):
    answer = question.ask()
    if answer is None:
        raise Cancelled
    return answer


def live_hint(describe, low: int, high: int):
    """A right-hand prompt recomputed on every keystroke.

    Anything going wrong here must leave the prompt usable, so a bad number or
    a failed lookup simply shows nothing.
    """

    def rprompt():
        try:
            value = int(get_app().current_buffer.text.strip())
            if not low <= value <= high:
                return ""
            return FormattedText([("fg:#8b949e", f"  {describe(value)} ")])
        except Exception:
            return ""

    return rprompt


def ask_int(message: str, default: int, low: int, high: int, describe=None) -> int:
    def validate(text: str) -> bool | str:
        try:
            value = int(text)
        except ValueError:
            return "Enter a whole number"
        if not low <= value <= high:
            return f"Enter a number from {low} to {high}"
        return True

    extra = {"rprompt": live_hint(describe, low, high)} if describe else {}
    return int(
        ask(
            questionary.text(
                message, default=str(default), validate=validate, style=STYLE, **extra
            )
        )
    )


def ask_path(console, message: str, default: str | None = None) -> Path:
    """Prompt for a path, forgiving the ways terminals mangle one."""
    kwargs = {"style": STYLE}
    if default is not None:
        kwargs["default"] = default
    while True:
        try:
            return clean_path_input(ask(questionary.path(message, **kwargs)))
        except ValueError:
            console.print("[red]Please enter a path.[/red]")


def pause(message: str = "  Press any key to return to the menu…") -> None:
    try:
        questionary.press_any_key_to_continue(message, style=STYLE).ask()
    except Exception:
        pass  # never let a cosmetic pause break a completed run
