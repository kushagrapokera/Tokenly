"""Responsive plain-text tables for the terminal report.

Width is measured every time a table is drawn rather than once at startup, so narrowing
the terminal is picked up by the next report instead of the next run. When the window
cannot hold every column, the least important ones are dropped rather than letting the
table wrap into ragged unreadable lines, so the same command reads well in a narrow
split pane and in a full-screen window.

Plain ASCII only. The command has to survive a Windows cp1252 console, where
box-drawing characters are not encodable, so the rules are dashes and the gutters are
spaces.
"""

from __future__ import annotations

import shutil
from collections.abc import Collection, Sequence
from dataclasses import dataclass

MINIMUM_WIDTH = 46
FALLBACK_WIDTH = 100
FALLBACK_HEIGHT = 24

GUTTER = "  "
EDGE = "| "
SEPARATOR = " | "
TAIL = " |"
RULE_JOIN = "+"
RULE_FILL = "-"

# A row is "| " + cell + " | " per column, closed off by a trailing " |", so each column
# costs the width of its cell plus those three characters.
CELL_PADDING = len(EDGE) + 1

# A priority of 1 is never dropped: it is the row's identity and the number the reader
# came for. Higher numbers are safer to lose, and the largest goes first.
NEVER_DROPPED = 1

# A squeezed column is never taken below this, so a number cannot be cut into nonsense.
FLOOR = 4
ELLIPSIS = "~"


@dataclass(frozen=True)
class Column:
    """One column of a table: its heading, how it lines up, and how much it matters.

    `priority` is what makes a table responsive. When the terminal is too narrow for
    everything, the column with the highest priority is dropped first; priority 1
    columns survive at any width.
    """

    heading: str
    right: bool = True
    priority: int = NEVER_DROPPED


def terminal_width(override: int | None = None) -> int:
    """Return the usable width, measured fresh on every call so resizing takes effect.

    `shutil.get_terminal_size` also honours the COLUMNS environment variable, which is
    what makes the narrow-terminal behaviour testable without a real terminal.
    """
    if override is not None:
        return max(MINIMUM_WIDTH, override)
    columns = shutil.get_terminal_size((FALLBACK_WIDTH, FALLBACK_HEIGHT)).columns
    return max(MINIMUM_WIDTH, columns)


def render(
    columns: Sequence[Column],
    rows: Sequence[Sequence[str]],
    width: int | None = None,
) -> list[str]:
    """Draw a table that fits `width`, dropping the least important columns if needed.

    Returns the finished lines, already indented. Cells arrive as text: this module lays
    out, it does not decide how a number is written.
    """
    if not columns or not rows:
        return []

    usable = terminal_width(width) - len(GUTTER)
    kept = _fit(columns, rows, usable)
    widths = _squeeze(_natural(columns, rows, kept), usable)

    heading_row = _row(columns, (), kept, widths, heading=True)
    rule = _rule(heading_row)
    body = [_row(columns, row, kept, widths) for row in rows]
    return [rule, heading_row, rule, *body, rule]


def print_table(
    columns: Sequence[Column],
    rows: Sequence[Sequence[str]],
    width: int | None = None,
) -> None:
    """Render a table and write it out one line at a time."""
    for line in render(columns, rows, width):
        print(line)


def _natural(
    columns: Sequence[Column],
    rows: Sequence[Sequence[str]],
    kept: Collection[int],
) -> dict[int, int]:
    """Return each kept column's natural width, before any squeezing."""
    widths = {index: len(columns[index].heading) for index in kept}
    for row in rows:
        for index in kept:
            widths[index] = max(widths[index], len(row[index]))
    return widths


def _fit(columns: Sequence[Column], rows: Sequence[Sequence[str]], usable: int) -> list[int]:
    """Choose which columns survive at this width, dropping the least important first."""
    kept = set(range(len(columns)))
    droppable = sorted(
        (index for index in kept if columns[index].priority > NEVER_DROPPED),
        key=lambda index: -columns[index].priority,
    )
    while len(kept) > 1 and _total(_natural(columns, rows, kept)) > usable:
        if not droppable:
            break
        kept.discard(droppable.pop(0))
    return sorted(kept)


def _squeeze(widths: dict[int, int], usable: int) -> dict[int, int]:
    """Trim the widest columns until the table fits, so the loss is shared around.

    Dropping a whole column is worse than making several a little narrower, so this runs
    after columns have already been discarded and only closes the remaining gap.
    """
    while _total(widths) > usable and widths:
        widest = max(widths, key=lambda index: widths[index])
        if widths[widest] <= FLOOR:
            break
        widths[widest] -= 1
    return widths


def _total(widths: dict[int, int]) -> int:
    """Return the printed width of a table with the given column widths."""
    return sum(width + CELL_PADDING for width in widths.values()) + len(TAIL) - 1


def _rule(sample: str) -> str:
    """Return a horizontal rule matching an already-rendered row exactly.

    Deriving it from the row itself means the joins land on the verticals by
    construction, so the two cannot drift apart when the column widths change. Only the
    gutter stays blank; everything between the outer verticals is solid, so the blank
    padding a right-aligned number carries does not punch holes in the rule.
    """
    head = sample[: len(GUTTER)]
    body = [
        RULE_JOIN if character == EDGE[0] else RULE_FILL for character in sample[len(GUTTER) :]
    ]
    return head + "".join(body)


def _row(
    columns: Sequence[Column],
    row: Sequence[str],
    kept: Sequence[int],
    widths: dict[int, int],
    heading: bool = False,
) -> str:
    """Return one row of the table, padded out to the column widths."""
    cells = []
    for index in kept:
        column = columns[index]
        width = widths[index]
        text = column.heading if heading else _shorten(row[index], width)
        cells.append(text.rjust(width) if column.right else text.ljust(width))
    return GUTTER + EDGE + SEPARATOR.join(cells) + TAIL


def _shorten(text: str, width: int) -> str:
    """Trim text to fit, marking anything cut with a trailing character."""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + ELLIPSIS