"""The look of a toolkit: its banner and its card menu."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from rich.text import Text

from .banner import GRADIENT_END, GRADIENT_START, banner_lines, gradient_colors, subtitle_for
from .menu import MenuItem, columns_for, next_index, render_grid
from .prompts import Cancelled

CARD_LINES_PER_ROW = 5  # four card lines plus the gap beneath


def gradient_line(line: str) -> Text:
    """One banner row, its colour sliding left to right across the glyphs."""
    text = Text()
    for char, rgb in zip(line, gradient_colors(len(line), GRADIENT_START, GRADIENT_END)):
        text.append(char, style=f"rgb({rgb[0]},{rgb[1]},{rgb[2]})")
    return text


def print_banner(console, title: str, subtitle: str) -> None:
    width = console.width
    console.print()
    for line in banner_lines(width, title):
        console.print(gradient_line(line))
    tagline = subtitle_for(width, subtitle)
    if tagline:
        console.print(Text(tagline.center(width), style="dim"))
    console.print(gradient_line("─" * width))
    console.print()


def choose_from_cards(console, items: list[MenuItem], question: str) -> str:
    """A grid of cards, driven by the arrow keys or a number.

    questionary only draws a vertical list, so this is a small prompt_toolkit
    application of its own. All the geometry lives in `menu`.
    """
    state = {"selected": 0}

    def terminal_width() -> int:
        return get_app().output.get_size().columns

    def grid():
        fragments: list[tuple[str, str]] = []
        for line in render_grid(items, state["selected"], terminal_width()):
            fragments.extend(line)
            fragments.append(("", "\n"))
        return fragments[:-1]

    def grid_height() -> Dimension:
        rows = -(-len(items) // columns_for(terminal_width()))
        return Dimension.exact(rows * CARD_LINES_PER_ROW - 1)

    bindings = KeyBindings()

    for key, direction in (("left", "left"), ("right", "right"), ("up", "up"), ("down", "down")):
        @bindings.add(key)
        def _(event, direction=direction) -> None:
            state["selected"] = next_index(
                state["selected"], direction,
                count=len(items), columns=columns_for(terminal_width()),
            )

    @bindings.add("tab")
    def _(event) -> None:
        state["selected"] = (state["selected"] + 1) % len(items)

    @bindings.add("s-tab")
    def _(event) -> None:
        state["selected"] = (state["selected"] - 1) % len(items)

    for position in range(len(items)):
        @bindings.add(str(position + 1))
        def _(event, position=position) -> None:
            state["selected"] = position
            event.app.exit(result=items[position].key)

    @bindings.add("enter")
    def _(event) -> None:
        event.app.exit(result=items[state["selected"]].key)

    @bindings.add("c-c")
    @bindings.add("escape")
    def _(event) -> None:
        event.app.exit(result=None)

    application = Application(
        layout=Layout(
            HSplit([
                Window(
                    FormattedTextControl(lambda: [("bold", f"  {question}")]),
                    height=Dimension.exact(2),
                ),
                Window(FormattedTextControl(grid), height=grid_height),
                Window(
                    FormattedTextControl(lambda: [(
                        "fg:#6e7681",
                        f"\n  ↑ ↓ ← → move    1-{len(items)} jump straight there"
                        "    enter select    esc quit",
                    )]),
                    height=Dimension.exact(2),
                ),
            ])
        ),
        key_bindings=bindings,
        full_screen=False,
        erase_when_done=True,
    )

    chosen = application.run()
    if chosen is None:
        raise Cancelled
    return chosen
