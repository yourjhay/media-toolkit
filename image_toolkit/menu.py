"""A grid of bordered cards, one per operation.

Pure layout: given the items, which one is selected and how wide the terminal
is, produce styled lines. No terminal, no key handling, so the geometry can be
checked in tests. `tui` feeds the result to prompt_toolkit.
"""

from __future__ import annotations

from dataclasses import dataclass

Fragment = tuple[str, str]
Line = list[Fragment]

MIN_CARD_WIDTH = 26
MAX_CARD_WIDTH = 44
CARD_GAP = 3
MAX_COLUMNS = 2

# Light box for a resting card, heavy for the selected one, so the selection
# survives a terminal with no colour.
_LIGHT = {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"}
_HEAVY = {"tl": "┏", "tr": "┓", "bl": "┗", "br": "┛", "h": "━", "v": "┃"}


@dataclass
class MenuItem:
    key: str
    title: str
    detail: str
    color: str


def plain(line: Line) -> str:
    """The text of a styled line, with the styles dropped."""
    return "".join(text for _, text in line)


def columns_for(width: int) -> int:
    if width >= MIN_CARD_WIDTH * 2 + CARD_GAP:
        return MAX_COLUMNS
    return 1


def card_width_for(width: int, columns: int) -> int:
    available = (width - CARD_GAP * (columns - 1)) // columns
    return max(MIN_CARD_WIDTH, min(MAX_CARD_WIDTH, available))


def next_index(current: int, direction: str, count: int, columns: int) -> int:
    """Move the selection, stopping at the edges rather than wrapping."""
    steps = {"left": -1, "right": 1, "up": -columns, "down": columns}
    if direction not in steps:
        return current
    target = current + steps[direction]
    if not 0 <= target < count:
        # Moving down off the end lands on the last card rather than nowhere.
        if direction == "down" and current < count - 1:
            return count - 1
        return current
    return target


def _fit(text: str, width: int) -> str:
    if len(text) <= width:
        return text.ljust(width)
    return (text[: max(0, width - 1)] + "…") if width > 0 else ""


def _card(item: MenuItem, number: int, selected: bool, width: int) -> list[Line]:
    """One card, as four styled lines of exactly `width` characters."""
    box = _HEAVY if selected else _LIGHT
    border = f"fg:{item.color}" + (" bold" if selected else "")
    title_style = f"fg:{item.color} bold" if selected else "fg:#c9d1d9"
    detail_style = f"fg:{item.color}" if selected else "fg:#6e7681"

    label = f" {number} "
    top = box["tl"] + box["h"] + label + box["h"] * (width - 3 - len(label)) + box["tr"]
    bottom = box["bl"] + box["h"] * (width - 2) + box["br"]
    inner = width - 4

    def row(text: str, style: str) -> Line:
        return [
            (border, box["v"] + " "),
            (style, _fit(text, inner)),
            (border, " " + box["v"]),
        ]

    return [
        [(border, top)],
        row(item.title, title_style),
        row(item.detail, detail_style),
        [(border, bottom)],
    ]


def render_grid(items: list[MenuItem], selected: int, width: int) -> list[Line]:
    """Lay the cards out in a grid, every line padded to the same length."""
    columns = columns_for(width)
    card_width = card_width_for(width, columns)
    gap = CARD_GAP if columns > 1 else 0
    total = card_width * columns + gap * (columns - 1)

    lines: list[Line] = []
    for start in range(0, len(items), columns):
        row_items = items[start : start + columns]
        cards = [
            _card(item, start + offset + 1, start + offset == selected, card_width)
            for offset, item in enumerate(row_items)
        ]
        blank = [[("", " " * card_width)] for _ in range(4)]
        cards += [blank] * (columns - len(cards))

        for line_no in range(4):
            line: Line = []
            for column, card in enumerate(cards):
                if column:
                    line.append(("", " " * gap))
                line.extend(card[line_no])
            lines.append(line)
        lines.append([("", " " * total)])

    return lines[:-1] if lines else lines
