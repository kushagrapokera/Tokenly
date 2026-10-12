"""Totals for one time window, with incomplete coverage reported separately.

NULLs are the key subtlety: an `unavailable` record stores `None`, not 0, and
`SUM` skips NULLs on its own. But a plain `SUM` cannot tell "no usage" from
"no data", so this module also counts how many records in the window carry a
known total versus an unknown one. `reported_total_tokens` is the honest sum;
`unknown_total_events` says how much of the picture is missing.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aggregation.cache import CacheMetrics, cache_group_columns, metrics_from_grouped_row
from aggregation.filters import UsageFilter, filter_conditions
from aggregation.windows import TimeWindow
from database.models import UsageEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageSummary:
    """Token totals for one window, plus how many rows each figure rests on."""

    window_label: str
    request_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    consumption_tokens: int
    known_total_events: int
    unknown_total_events: int
    cache: CacheMetrics = CacheMetrics()


def summarize_range(
    session: Session, window: TimeWindow, filters: UsageFilter | None = None
) -> UsageSummary:
    """Sum every token column over the window's half-open `[start, end)` bounds."""
    active = filters or UsageFilter()
    statement = select(
        func.count().label("request_count"),
        func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(UsageEvent.consumption_tokens), 0).label("consumption_tokens"),
        func.count(UsageEvent.total_tokens).label("known_total_events"),
        (func.count() - func.count(UsageEvent.total_tokens)).label("unknown_total_events"),
        *cache_group_columns(),
    )
    conditions = filter_conditions(active)
    if window.start is not None:
        conditions.append(UsageEvent.timestamp >= window.start)
    if window.end is not None:
        conditions.append(UsageEvent.timestamp < window.end)
    if conditions:
        statement = statement.where(*conditions)

    row = session.execute(statement).one()
    summary = UsageSummary(
        window_label=window.label,
        request_count=int(row.request_count),
        input_tokens=int(row.input_tokens),
        output_tokens=int(row.output_tokens),
        total_tokens=int(row.total_tokens),
        consumption_tokens=int(row.consumption_tokens),
        known_total_events=int(row.known_total_events),
        unknown_total_events=int(row.unknown_total_events),
        cache=metrics_from_grouped_row(row, int(row.request_count)),
    )
    logger.info(
        "summarized window %s: %d requests, %d total tokens (%d unknown)",
        window.label,
        summary.request_count,
        summary.total_tokens,
        summary.unknown_total_events,
    )
    return summary
