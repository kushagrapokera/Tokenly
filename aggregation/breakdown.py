"""Per-model token usage, grouped so providers and platforms never blur together.

The group key is `(platform, provider_id, model_id)`. Two providers can both serve a
model called "sonnet", and attributing one's usage to the other would be wrong; the
same holds for one model name reached through two different assistants. This matches
how a usage event is identified everywhere else — Phase 1 §5 settles on
`(provider, model)` per platform, and the plan requires the dashboard to show the
platform, the provider, and the model side by side.

Grouping by provider and model alone would merge the two platforms' rows whenever
they happen to share a model name, which is exactly the attribution error the
platform column exists to prevent.
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
    """Totals for one (platform, provider, model) combination inside a window."""

    platform: str
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
    """Return one row per (platform, provider, model) in the window, ordered by total."""
    active = filters or UsageFilter()
    statement = (
        select(
            UsageEvent.platform,
            UsageEvent.provider_id,
            UsageEvent.model_id,
            func.count().label("request_count"),
            func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(UsageEvent.consumption_tokens), 0).label("consumption_tokens"),
            (func.count() - func.count(UsageEvent.total_tokens)).label("unknown_total_events"),
        )
        .group_by(UsageEvent.platform, UsageEvent.provider_id, UsageEvent.model_id)
        .order_by(
            func.coalesce(func.sum(UsageEvent.total_tokens), 0).desc(),
            UsageEvent.platform,
            UsageEvent.model_id,
        )
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
            platform=str(row.platform),
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
    logger.info("model breakdown for %s found %d model rows", window.label, len(result))
    return result
