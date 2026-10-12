"""Named ranges the dashboard can ask for, mapped onto time windows.

The API speaks in range names ("today", "last_7_days") rather than raw UTC bounds, so
a client never has to know how calendar edges are built or in which timezone they
belong. Each name resolves through `aggregation.windows`, which keeps every calendar
boundary in the user's timezone.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from aggregation.windows import (
    TimeWindow,
    all_time_window,
    current_month_window,
    current_year_window,
    custom_window,
    last_7_days_window,
    previous_month_window,
    today_window,
    yesterday_window,
)
from errors.exceptions import UnknownRangeError

logger = logging.getLogger(__name__)

RANGE_TODAY = "today"
RANGE_YESTERDAY = "yesterday"
RANGE_LAST_7_DAYS = "last_7_days"
RANGE_CURRENT_MONTH = "current_month"
RANGE_PREVIOUS_MONTH = "previous_month"
RANGE_CURRENT_YEAR = "current_year"
RANGE_ALL_TIME = "all_time"
RANGE_CUSTOM = "custom"

WindowBuilder = Callable[[str], TimeWindow]


def _all_time_range_builder(zone: str) -> TimeWindow:
    """Return the unbounded window, keeping the requested timezone for the client.

    The bounds are None either way, but the timezone is echoed back so a response says
    which calendar the client asked in even when no calendar boundary is involved.
    """
    window = all_time_window()
    return TimeWindow(
        label=window.label,
        start=window.start,
        end=window.end,
        timezone_name=zone,
    )


@dataclass(frozen=True)
class NamedRange:
    """One range the API accepts, with the window builder that produces it.

    `build` is None exactly for a range whose window comes from caller-supplied bounds
    rather than from the calendar. `resolve_range` handles that case directly, so there
    is deliberately no builder to call and nothing falls through to a wrong window.
    """

    name: str
    build: WindowBuilder | None
    description: str


NAMED_RANGES: tuple[NamedRange, ...] = (
    NamedRange(RANGE_TODAY, lambda zone: today_window(zone), "Today, in the requested timezone"),
    NamedRange(
        RANGE_YESTERDAY, lambda zone: yesterday_window(zone), "Yesterday, in the requested timezone"
    ),
    NamedRange(
        RANGE_LAST_7_DAYS,
        lambda zone: last_7_days_window(zone),
        "The last seven calendar days including today",
    ),
    NamedRange(
        RANGE_CURRENT_MONTH,
        lambda zone: current_month_window(zone),
        "The current calendar month",
    ),
    NamedRange(
        RANGE_PREVIOUS_MONTH,
        lambda zone: previous_month_window(zone),
        "The previous calendar month",
    ),
    NamedRange(
        RANGE_CURRENT_YEAR,
        lambda zone: current_year_window(zone),
        "The current calendar year",
    ),
    NamedRange(
        RANGE_ALL_TIME,
        _all_time_range_builder,
        "Every stored usage event",
    ),
    NamedRange(
        RANGE_CUSTOM,
        None,
        "A caller-supplied start and end",
    ),
)

DEFAULT_RANGE = RANGE_TODAY

RANGE_NAMES: tuple[str, ...] = tuple(named.name for named in NAMED_RANGES)


def find_range(range_name: str) -> NamedRange:
    """Return the named range, or raise `UnknownRangeError` listing the valid names."""
    for named in NAMED_RANGES:
        if named.name == range_name:
            return named
    logger.warning("rejected unknown range %r", range_name)
    raise UnknownRangeError(range_name, RANGE_NAMES)


def resolve_range(
    range_name: str,
    timezone_name: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> TimeWindow:
    """Build the window for a named range, validating custom bounds on the way.

    Only the custom range uses `start` and `end`; the named ranges ignore them so a
    client sending stale bounds does not silently get a window it did not ask for.
    """
    named = find_range(range_name)
    if named.build is None:
        window = custom_window(start, end, timezone_name)
        logger.debug("resolved custom range to %s to %s", window.start, window.end)
        return window
    window = named.build(timezone_name)
    logger.debug("resolved range %s to %s to %s", range_name, window.start, window.end)
    return window


def resolve_range_for_timeline(
    range_name: str,
    timezone_name: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> TimeWindow:
    """Build a window that can be split into buckets.

    Bucketing needs finite edges. All-time has none, so it is narrowed to the current
    year rather than refused: the dashboard asks for all-time usage and still deserves
    a chart.
    """
    window = resolve_range(range_name, timezone_name, start=start, end=end)
    if window.start is None or window.end is None:
        logger.info("range %s is unbounded; using the current year for bucketing", range_name)
        return current_year_window(timezone_name)
    return window
