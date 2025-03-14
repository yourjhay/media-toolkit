"""Question-asking that any toolkit in this repo can reuse.

No colours, layout or wording specific to images or video: those belong to
whichever toolkit is asking.
"""

from __future__ import annotations

from pathlib import Path

import questionary
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings

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
    """The user pressed Ctrl-C: they want out of the tool."""


class GoBack(Exception):
    """The user wants this question dropped and the menu back.

    Deliberately not a kind of Cancelled: one returns to the menu, the other
    ends the session, and catching them together would merge the two.
    """


def ask_text_or_back(
    message: str,
    default: str = "",
    style=None,
    asker=None,
    instruction: str = "esc or blank to go back",
) -> str:
    """Ask for some text, with a way out that is not quitting.

    Escape is bound explicitly because a questionary text prompt does not treat
    it as a cancel — it is the prefix byte for escape sequences, so on its own
    it does nothing at all. Submitting an empty line means the same thing, and
    is the gesture most people try first.
    """
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def _(event) -> None:
        event.app.exit(result="")

    ask_for = asker or questionary.text
    answer = ask(
        ask_for(
            message, default=default, style=style or STYLE,
            instruction=instruction, key_bindings=bindings,
        )
    )
    if not answer.strip():
        raise GoBack
    return answer


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


def ask_path(console, message: str, default: str | None = None, allow_back: bool = True) -> Path:
    """Prompt for a path, forgiving the ways terminals mangle one.

    Escape is not bound here: questionary.path supplies its own key bindings
    for completion and will not take a second set. An empty line is the way
    back, which is also the gesture most people try first.
    """
    kwargs = {"style": STYLE}
    if default is not None:
        kwargs["default"] = default
    while True:
        raw = ask(questionary.path(message, **kwargs))
        if allow_back and not raw.strip():
            raise GoBack
        try:
            return clean_path_input(raw)
        except ValueError:
            console.print("[red]Please enter a path.[/red]")


def pause(message: str = "  Press any key to return to the menu…") -> None:
    try:
        questionary.press_any_key_to_continue(message, style=STYLE).ask()
    except Exception:
        pass  # never let a cosmetic pause break a completed run
