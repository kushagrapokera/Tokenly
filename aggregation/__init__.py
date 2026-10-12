"""Usage aggregation: time-windowed and model-wise token totals.

Phase 7 turns stored usage events into the numbers the dashboard shows. Every
aggregation follows the same rules: calendar boundaries come from the user's
selected timezone, timestamps are stored and compared in UTC, intervals are
half-open (`start <= timestamp < end`), unknown token counts stay out of the
sums, and incomplete coverage is reported alongside the totals, never hidden.
"""

from aggregation.breakdown import ModelUsage, breakdown_by_model
from aggregation.cache import CacheMetrics
from aggregation.filters import UsageFilter, filter_conditions
from aggregation.ranges import (
    DEFAULT_RANGE,
    RANGE_NAMES,
    NamedRange,
    find_range,
    resolve_range,
    resolve_range_for_timeline,
)
from aggregation.summary import UsageSummary, summarize_range
from aggregation.timeline import TimeBucket, bucket_timeline
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

__all__ = [
    "DEFAULT_RANGE",
    "RANGE_NAMES",
    "CacheMetrics",
    "ModelUsage",
    "NamedRange",
    "TimeBucket",
    "TimeWindow",
    "UsageFilter",
    "UsageSummary",
    "all_time_window",
    "breakdown_by_model",
    "bucket_timeline",
    "current_month_window",
    "current_year_window",
    "custom_window",
    "filter_conditions",
    "find_range",
    "last_7_days_window",
    "previous_month_window",
    "resolve_range",
    "resolve_range_for_timeline",
    "summarize_range",
    "today_window",
    "yesterday_window",
]
