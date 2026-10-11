"""Window tests: calendar boundaries, timezones, half-open edges, errors."""

from datetime import datetime, timezone

import pytest

from aggregation import (
    all_time_window,
    current_month_window,
    current_year_window,
    custom_window,
    last_7_days_window,
    previous_month_window,
    today_window,
    yesterday_window,
)
from errors.exceptions import InvalidTimeRangeError, InvalidTimezoneError

UTC = timezone.utc
NOON_OCT11 = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def test_today_window_covers_one_utc_day() -> None:
    window = today_window("UTC", now=NOON_OCT11)

    assert window.label == "today"
    assert window.start == datetime(2026, 10, 11, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 12, 0, 0, tzinfo=UTC)


def test_yesterday_window_is_the_day_before_today() -> None:
    window = yesterday_window("UTC", now=NOON_OCT11)

    assert window.start == datetime(2026, 10, 10, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 11, 0, 0, tzinfo=UTC)


def test_today_and_yesterday_are_adjacent_half_open_windows() -> None:
    today = today_window("UTC", now=NOON_OCT11)
    yesterday = yesterday_window("UTC", now=NOON_OCT11)

    assert yesterday.start is not None
    assert yesterday.end is not None
    assert today.end is not None
    assert yesterday.end == today.start
    assert yesterday.start < yesterday.end <= today.end


def test_last_7_days_window_spans_seven_midnights() -> None:
    window = last_7_days_window("UTC", now=NOON_OCT11)

    assert window.start == datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 12, 0, 0, tzinfo=UTC)


def test_current_month_window() -> None:
    window = current_month_window("UTC", now=NOON_OCT11)

    assert window.start == datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 11, 1, 0, 0, tzinfo=UTC)


def test_previous_month_window() -> None:
    window = previous_month_window("UTC", now=NOON_OCT11)

    assert window.start == datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def test_previous_month_window_wraps_the_year() -> None:
    january = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    window = previous_month_window("UTC", now=january)

    assert window.start == datetime(2025, 12, 1, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def test_current_year_window() -> None:
    window = current_year_window("UTC", now=NOON_OCT11)

    assert window.start == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2027, 1, 1, 0, 0, tzinfo=UTC)


def test_all_time_window_is_unbounded() -> None:
    window = all_time_window()

    assert window.label == "all_time"
    assert window.start is None
    assert window.end is None


def test_timezone_shifts_midnight_to_utc() -> None:
    """Midnight in Kolkata is the previous evening in UTC."""
    window = today_window("Asia/Kolkata", now=NOON_OCT11)

    assert window.start is not None and window.end is not None
    assert window.start.utcoffset() == UTC.utcoffset(None)
    assert window.start.hour == 18 and window.start.day == 10
    assert window.end.hour == 18 and window.end.day == 11


def test_unknown_timezone_raises_a_named_error() -> None:
    with pytest.raises(InvalidTimezoneError):
        today_window("Mars/Olympus")


def test_custom_window_normalizes_bounds_to_utc() -> None:
    from zoneinfo import ZoneInfo

    kolkata = ZoneInfo("Asia/Kolkata")
    start = datetime(2026, 10, 1, 0, 0, tzinfo=kolkata)
    end = datetime(2026, 10, 8, 0, 0, tzinfo=kolkata)
    window = custom_window(start, end)

    assert window.label == "custom"
    assert window.start == datetime(2026, 9, 30, 18, 30, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 7, 18, 30, tzinfo=UTC)


def test_custom_window_rejects_an_inverted_range() -> None:
    with pytest.raises(InvalidTimeRangeError):
        custom_window(NOON_OCT11, NOON_OCT11)


def test_custom_window_rejects_a_missing_bound() -> None:
    with pytest.raises(InvalidTimeRangeError):
        custom_window(None, NOON_OCT11)
