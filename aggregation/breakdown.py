"""Per-model token usage, grouped so providers never blur together.

The group key is `(provider_id, model_id)`: two providers can both serve a
model called "sonnet", and attributing one's usage to the other would be wrong.
This matches the Phase 7 SQL sketch (`GROUP BY provider_id, model_id`) with the
addition of a request count and an unknown-coverage count per model.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aggregation.filters import UsageFilter, filter_conditions
from aggregation.windows import TimeWindow
from database.models import UsageEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelUsage:
    """Totals for one (provider, model) pair inside a window."""

    provider_id: str
    model_id: str
    request_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    consumption_tokens: int
    unknown_total_events: int


def breakdown_by_model(
    session: Session, window: TimeWindow, filters: UsageFilter | None = None
) -> list[ModelUsage]:
    """Return one row per (provider, model) pair in the window, ordered by total."""
    active = filters or UsageFilter()
    statement = (
        select(
            UsageEvent.provider_id,
            UsageEvent.model_id,
            func.count().label("request_count"),
            func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(UsageEvent.consumption_tokens), 0).label("consumption_tokens"),
            (func.count() - func.count(UsageEvent.total_tokens)).label("unknown_total_events"),
        )
        .group_by(UsageEvent.provider_id, UsageEvent.model_id)
        .order_by(func.coalesce(func.sum(UsageEvent.total_tokens), 0).desc())
    )
    conditions = filter_conditions(active)
    if window.start is not None:
        conditions.append(UsageEvent.timestamp >= window.start)
    if window.end is not None:
        conditions.append(UsageEvent.timestamp < window.end)
    if conditions:
        statement = statement.where(*conditions)

    rows = session.execute(statement).all()
    result = [
        ModelUsage(
            provider_id=str(row.provider_id),
            model_id=str(row.model_id),
            request_count=int(row.request_count),
            input_tokens=int(row.input_tokens),
            output_tokens=int(row.output_tokens),
            total_tokens=int(row.total_tokens),
            consumption_tokens=int(row.consumption_tokens),
            unknown_total_events=int(row.unknown_total_events),
        )
        for row in rows
    ]
    logger.info("model breakdown for %s found %d models", window.label, len(result))
    return result
