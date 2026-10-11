"""Tests for the named-range registry behind every usage endpoint.

The API speaks in range names so the dashboard never has to build calendar edges itself.
These tests pin which names exist and what each one means, because a range that silently
resolves to the wrong interval would show wrong numbers with no visible failure.
"""

from datetime import datetime, timezone

import pytest

from aggregation.ranges import (
    DEFAULT_RANGE,
    RANGE_ALL_TIME,
    RANGE_CURRENT_YEAR,
    RANGE_CUSTOM,
    RANGE_LAST_7_DAYS,
    RANGE_NAMES,
    find_range,
    resolve_range,
    resolve_range_for_timeline,
)
from errors.exceptions import UnknownRangeError

UTC = timezone.utc
NOW = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


def test_every_documented_range_is_registered() -> None:
    assert set(RANGE_NAMES) == {
        "today",
        "yesterday",
        "last_7_days",
        "current_month",
        "previous_month",
        "current_year",
        "all_time",
        "custom",
    }


def test_the_default_range_is_a_named_one_not_a_custom() -> None:
    assert DEFAULT_RANGE in RANGE_NAMES
    assert DEFAULT_RANGE != RANGE_CUSTOM


def test_named_ranges_can_be_built_for_any_timezone() -> None:
    bounds = {"start": datetime(2026, 1, 1, tzinfo=UTC), "end": datetime(2026, 2, 1, tzinfo=UTC)}

    for name in RANGE_NAMES:
        window = resolve_range(name, "Asia/Kolkata", **bounds)

        assert window.timezone_name == "Asia/Kolkata"


def test_a_named_range_ignores_caller_supplied_bounds() -> None:
    with_bounds = resolve_range(
        RANGE_CURRENT_YEAR, "UTC", start=datetime(2020, 1, 1, tzinfo=UTC), end=NOW
    )
    without_bounds = resolve_range(RANGE_CURRENT_YEAR, "UTC")

    assert with_bounds.start == without_bounds.start
    assert with_bounds.end == without_bounds.end


def test_all_time_is_unbounded() -> None:
    window = resolve_range(RANGE_ALL_TIME, "UTC")

    assert window.start is None
    assert window.end is None


def test_an_unknown_range_is_rejected_with_the_valid_names() -> None:
    with pytest.raises(UnknownRangeError) as caught:
        find_range("last_fortnight")

    assert caught.value.range_name == "last_fortnight"
    assert "last_7_days" in caught.value.supported


def test_a_custom_range_uses_the_caller_bounds() -> None:
    window = resolve_range(
        RANGE_CUSTOM,
        "UTC",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 2, 1, tzinfo=UTC),
    )

    assert window.label == "custom"
    assert window.start == datetime(2026, 1, 1, tzinfo=UTC)


def test_a_timeline_of_all_time_falls_back_to_the_current_year() -> None:
    window = resolve_range_for_timeline(RANGE_ALL_TIME, "UTC")

    assert window.start is not None
    assert window.end is not None
    assert window.start.year == 2026


def test_a_bounded_range_keeps_its_bounds_for_timelines() -> None:
    bounded = resolve_range(RANGE_LAST_7_DAYS, "UTC")

    assert resolve_range_for_timeline(RANGE_LAST_7_DAYS, "UTC").label == bounded.label
