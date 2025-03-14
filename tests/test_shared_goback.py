"""Getting out of a prompt without quitting the whole tool.

Escape is not a cancel key in a questionary text prompt — it is the prefix for
escape sequences, so pressing it does nothing and Enter on an empty line just
re-asks. That left the link prompt in a loop with no way back to the menu
short of Ctrl-C, which quits everything.
"""

import pytest

from shared.prompts import Cancelled, GoBack, ask_text_or_back


def _answers(*values):
    """A stand-in for questionary.text, handing back canned replies."""
    replies = list(values)

    class Question:
        def ask(self):
            return replies.pop(0)

    def asker(message, **kwargs):
        return Question()

    return asker


def test_an_answer_comes_back_as_given():
    assert ask_text_or_back("Link:", asker=_answers("https://example.com/a")) == "https://example.com/a"


def test_surrounding_space_does_not_make_an_answer_look_empty():
    assert ask_text_or_back("Link:", asker=_answers("  https://example.com/a  ")).strip() == "https://example.com/a"


def test_an_empty_answer_means_go_back():
    """Enter on an empty prompt is how people say "never mind"."""
    with pytest.raises(GoBack):
        ask_text_or_back("Link:", asker=_answers(""))


def test_a_whitespace_only_answer_means_go_back():
    with pytest.raises(GoBack):
        ask_text_or_back("Link:", asker=_answers("   "))


def test_ctrl_c_still_quits_rather_than_going_back():
    """The two gestures mean different things and must stay distinguishable."""
    with pytest.raises(Cancelled):
        ask_text_or_back("Link:", asker=_answers(None))


def test_go_back_is_not_a_cancellation():
    """main() catches Cancelled to exit; going back must not be caught by it."""
    assert not issubclass(GoBack, Cancelled)
    assert not issubclass(Cancelled, GoBack)


def test_escape_is_bound_on_the_prompt():
    """Without this the only way out is Ctrl-C, which quits the whole tool."""
    seen = {}

    class Question:
        def ask(self):
            return "x"

    def asker(message, **kwargs):
        seen.update(kwargs)
        return Question()

    ask_text_or_back("Link:", asker=asker)

    bindings = seen.get("key_bindings")
    assert bindings is not None
    keys = {str(binding.keys[0]) for binding in bindings.bindings}
    assert any("escape" in key.lower() for key in keys)
