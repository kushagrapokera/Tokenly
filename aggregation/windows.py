"""Calendar windows for usage aggregation.

A `TimeWindow` is a half-open interval `[start, end)` in UTC. The boundaries
are derived from calendar days in the user's selected timezone, because "today"
means something different in Tokyo than in New York, while the stored
timestamps are always UTC.

Half-open matters at the edges: an event exactly at `end` belongs to the next
window, so consecutive windows never share or skip a row. `None` on either side
means unbounded, which is how the all-time window reads everything.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from errors.exceptions import InvalidTimezoneError

logger = logging.getLogger(__name__)

UTC = timezone.utc


@dataclass(frozen=True)
class TimeWindow:
    """One half-open `[start, end)` interval, both bounds aware UTC datetimes."""

    label: str
    start: datetime | None
    end: datetime | None
    timezone_name: str = "UTC"


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    """Return the `ZoneInfo` for a user-selected name, or raise a named error."""
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        logger.warning("unknown timezone %r", timezone_name)
        raise InvalidTimezoneError(timezone_name) from error


def as_utc(moment: datetime) -> datetime:
    """Return the moment as an aware UTC datetime; naive values are assumed UTC."""
    if moment.tzinfo is None:
        logger.debug("naive datetime assumed to be UTC")
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _day_bounds(local_day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """Return the UTC bounds of one local calendar day, half-open."""
    start = datetime.combine(local_day, time.min).replace(tzinfo=zone).astimezone(UTC)
    end = datetime.combine(local_day + timedelta(days=1), time.min).replace(tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def _month_bounds(year: int, month: int, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """Return the UTC bounds of one local calendar month, half-open."""
    first_day = date(year, month, 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    start = datetime.combine(first_day, time.min).replace(tzinfo=zone).astimezone(UTC)
    end = (
        datetime.combine(date(next_year, next_month, 1), time.min)
        .replace(tzinfo=zone)
        .astimezone(UTC)
    )
    return start, end


def _local_today(zone: ZoneInfo, now: datetime | None) -> date:
    """Return today's date in the user's timezone."""
    moment = as_utc(now) if now is not None else datetime.now(UTC)
    return moment.astimezone(zone).date()


def today_window(timezone_name: str, now: datetime | None = None) -> TimeWindow:
    """Return midnight-to-midnight for today in the user's timezone, as UTC."""
    zone = resolve_timezone(timezone_name)
    start, end = _day_bounds(_local_today(zone, now), zone)
    logger.debug("today window in %s is %s to %s", timezone_name, start, end)
    return TimeWindow(label="today", start=start, end=end, timezone_name=timezone_name)


def yesterday_window(timezone_name: str, now: datetime | None = None) -> TimeWindow:
    """Return midnight-to-midnight for yesterday in the user's timezone, as UTC."""
    zone = resolve_timezone(timezone_name)
    start, end = _day_bounds(_local_today(zone, now) - timedelta(days=1), zone)
    logger.debug("yesterday window in %s is %s to %s", timezone_name, start, end)
    return TimeWindow(label="yesterday", start=start, end=end, timezone_name=timezone_name)


def last_7_days_window(timezone_name: str, now: datetime | None = None) -> TimeWindow:
    """Return the last seven full calendar days including today, as UTC bounds."""
    zone = resolve_timezone(timezone_name)
    today = _local_today(zone, now)
    start, _ = _day_bounds(today - timedelta(days=6), zone)
    _, end = _day_bounds(today, zone)
    logger.debug("last-7-days window in %s is %s to %s", timezone_name, start, end)
    return TimeWindow(label="last_7_days", start=start, end=end, timezone_name=timezone_name)


def current_month_window(timezone_name: str, now: datetime | None = None) -> TimeWindow:
    """Return the first of this month to the first of next month, as UTC bounds."""
    zone = resolve_timezone(timezone_name)
    today = _local_today(zone, now)
    start, end = _month_bounds(today.year, today.month, zone)
    logger.debug("current-month window in %s is %s to %s", timezone_name, start, end)
    return TimeWindow(label="current_month", start=start, end=end, timezone_name=timezone_name)


def previous_month_window(timezone_name: str, now: datetime | None = None) -> TimeWindow:
    """Return the whole previous calendar month in the user's timezone, as UTC."""
    zone = resolve_timezone(timezone_name)
    today = _local_today(zone, now)
    year, month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    start, end = _month_bounds(year, month, zone)
    logger.debug("previous-month window in %s is %s to %s", timezone_name, start, end)
    return TimeWindow(label="previous_month", start=start, end=end, timezone_name=timezone_name)


def current_year_window(timezone_name: str, now: datetime | None = None) -> TimeWindow:
    """Return January 1st to next January 1st in the user's timezone, as UTC."""
    zone = resolve_timezone(timezone_name)
    year = _local_today(zone, now).year
    start = datetime.combine(date(year, 1, 1), time.min).replace(tzinfo=zone).astimezone(UTC)
    end = datetime.combine(date(year + 1, 1, 1), time.min).replace(tzinfo=zone).astimezone(UTC)
    logger.debug("current-year window in %s is %s to %s", timezone_name, start, end)
    return TimeWindow(label="current_year", start=start, end=end, timezone_name=timezone_name)


def all_time_window() -> TimeWindow:
    """Return the unbounded window that reads every stored usage event."""
    logger.debug("all-time window selected")
    return TimeWindow(label="all_time", start=None, end=None)


def custom_window(
    start: datetime | None,
    end: datetime | None,
    timezone_name: str = "UTC",
) -> TimeWindow:
    """Return a caller-supplied half-open window, normalized to UTC.

    Both bounds must be present and ordered; an inverted or open-ended custom
    range is rejected rather than silently returning the wrong rows.
    """
    from errors.exceptions import InvalidTimeRangeError

    resolve_timezone(timezone_name)
    if start is None or end is None:
        raise InvalidTimeRangeError("custom ranges need both a start and an end")
    utc_start, utc_end = as_utc(start), as_utc(end)
    if utc_start >= utc_end:
        raise InvalidTimeRangeError(f"start {utc_start} is not before end {utc_end}")
    logger.debug("custom window is %s to %s", utc_start, utc_end)
    return TimeWindow(label="custom", start=utc_start, end=utc_end, timezone_name=timezone_name)
