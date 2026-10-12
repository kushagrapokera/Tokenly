"""Tests for the responsive table renderer.

The behaviour worth pinning is that a table always fits the terminal and never loses the
columns that carry the row's identity. Everything else follows from those two promises.
"""

import pytest

from cli.tables import Column, render, terminal_width

WIDE = [
    Column("Window", right=False, priority=1),
    Column("Requests", priority=1),
    Column("Total", priority=1),
    Column("Input", priority=2),
    Column("Output", priority=2),
    Column("Consumption", priority=2),
    Column("HitRate", priority=3),
    Column("TokenHit", priority=3),
    Column("Hits", priority=4),
    Column("Misses", priority=4),
]

ROWS = [
    [
        "All time", "2,812", "7,347,419", "6,441,459", "905,960",
        "446,452,420", "99.3%", "98.6%", "2,792", "20",
    ],
    [
        "Today", "601", "1,518,630", "1,329,094", "189,536",
        "72,790,999", "99.8%", "98.2%", "600", "1",
    ],
]


def headings(lines: list[str]) -> list[str]:
    """Return the column headings of a rendered table."""
    return [cell.strip() for cell in lines[1].split("|") if cell.strip()]


@pytest.mark.parametrize("width", [46, 52, 64, 80, 100, 120, 160, 200])
def test_no_line_is_wider_than_the_terminal(width: int) -> None:
    lines = render(WIDE, ROWS, width=width)

    assert all(len(line) <= width for line in lines)


@pytest.mark.parametrize("width", [46, 52, 64, 80, 100, 120, 160, 200])
def test_the_essential_columns_survive_at_every_width(width: int) -> None:
    # A narrower table may lose detail, but never the row's identity or its headline
    # numbers, however tight the window gets.
    kept = headings(render(WIDE, ROWS, width=width))

    assert kept[:3] == ["Window", "Requests", "Total"]


def test_the_least_important_columns_go_first() -> None:
    wide = headings(render(WIDE, ROWS, width=200))
    narrow = headings(render(WIDE, ROWS, width=52))

    assert len(narrow) < len(wide)
    assert set(narrow).issubset(set(wide))
    assert "Misses" not in narrow


def test_every_row_keeps_its_numbers_aligned() -> None:
    lines = render(WIDE, ROWS, width=140)

    # Each rule lines up with the rows around it, so the verticals form columns.
    assert len({len(line) for line in lines}) == 1


def test_the_output_is_plain_ascii() -> None:
    # The command has to survive a Windows cp1252 console, where box drawing is not
    # encodable and would raise on print rather than merely look wrong.
    lines = render(WIDE, ROWS, width=140)

    assert all(character.isascii() for line in lines for character in line)


def test_an_over_long_cell_is_shortened_and_marked() -> None:
    columns = [Column("Name", right=False, priority=1)]
    rows = [["a-very-long-model-name-that-will-not-fit-anywhere-near-46-columns"]]

    body = render(columns, rows, width=46)[3]

    assert body.strip().startswith("|")
    assert "~" in body
    assert len(body) <= 46


def test_a_cell_that_already_fits_is_left_alone() -> None:
    columns = [Column("Name", right=False, priority=1)]
    rows = [["short"]]

    body = render(columns, rows, width=46)[3]

    assert "short" in body
    assert "~" not in body


def test_nothing_is_rendered_for_an_empty_table() -> None:
    assert render(WIDE, [], width=100) == []
    assert render([], ROWS, width=100) == []


def test_width_comes_from_the_environment_so_a_resize_is_picked_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLUMNS", "120")

    assert terminal_width() == 120

    monkeypatch.setenv("COLUMNS", "60")

    assert terminal_width() == 60


def test_a_narrow_terminal_never_reports_a_width_below_the_minimum() -> None:
    assert terminal_width(1) >= 46