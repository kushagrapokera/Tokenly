"""Shared query filters for every aggregation.

`UsageFilter` carries the dashboard's provider/model/platform dimensions in one
place, so summary, breakdown, and timeline filter identically instead of each
re-implementing the same WHERE clauses.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import ColumnExpressionArgument

from database.models import UsageEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageFilter:
    """Narrow an aggregation to one slice of the stored usage."""

    platform: str | None = None
    provider_id: str | None = None
    model_id: str | None = None


def filter_conditions(filters: UsageFilter) -> list[ColumnExpressionArgument[bool]]:
    """Return the WHERE conditions for a filter, so any SELECT can use them."""
    conditions: list[ColumnExpressionArgument[bool]] = []
    if filters.platform is not None:
        conditions.append(UsageEvent.platform == filters.platform)
    if filters.provider_id is not None:
        conditions.append(UsageEvent.provider_id == filters.provider_id)
    if filters.model_id is not None:
        conditions.append(UsageEvent.model_id == filters.model_id)
    logger.debug("built %d filter conditions from %s", len(conditions), filters)
    return conditions
