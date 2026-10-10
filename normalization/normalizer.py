"""Token normalization: one entry point every collector uses to build a usage record.

Phase 4's rules live here and in the modules beside it:

  1. preserve the original provider and model identifiers -> untouched, passed through
  2. normalize timestamps to UTC                               -> `normalize_timestamp`
  3. use nonnegative integer token counts                      -> `read_count`
  4. represent unavailable values as null                      -> `None` throughout
  5. distinguish reported from estimated usage                 -> `resolve_usage_status`
  6. determine whether cached tokens overlap input             -> `CategoryRelationships`
  7. determine whether reasoning tokens overlap output         -> `CategoryRelationships`
  8. prevent overlapping categories being counted twice        -> `sum_every_category`
  9. preserve raw token metadata                              -> `raw_usage` passed through
"""

from collections.abc import Mapping
from datetime import datetime, timezone

from normalization.categories import (
    CategoryRelationships,
)
from normalization.status import resolve_usage_status
from normalization.totals import (
    TokenCategories,
    calculate_totals,
    token_categories_from_mapping,
)
from schemas.usage import UsageRecord

__all__ = [
    "CategoryRelationships",
    "TokenCategories",
    "calculate_totals",
    "normalize_timestamp",
    "normalize_usage_record",
    "resolve_usage_status",
    "token_categories_from_mapping",
]


def normalize_timestamp(moment: datetime) -> datetime:
    """Return the moment as an aware UTC datetime (rule 2)."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def normalize_usage_record(
    *,
    platform: str,
    provider_id: str,
    model_id: str,
    session_id: str,
    message_id: str,
    source_event_id: str,
    timestamp: datetime,
    raw_tokens: Mapping[str, object],
    raw_usage: Mapping[str, object] | None = None,
    relationships: CategoryRelationships,
    estimated: bool = False,
) -> UsageRecord:
    """Build a normalized usage record from a platform's raw token payload.

    Identity fields are passed through untouched (rule 1), the timestamp is forced to UTC
    (rule 2), and the original payload is preserved verbatim (rule 9).
    """
    categories = token_categories_from_mapping(raw_tokens)
    totals = calculate_totals(categories, relationships)
    status = resolve_usage_status(categories, estimated=estimated)

    return UsageRecord(
        platform=platform,
        provider_id=provider_id,
        model_id=model_id,
        session_id=session_id,
        message_id=message_id,
        source_event_id=source_event_id,
        timestamp=normalize_timestamp(timestamp),
        input_tokens=categories.input_tokens,
        output_tokens=categories.output_tokens,
        total_tokens=totals.total_tokens,
        reasoning_tokens=categories.reasoning_tokens,
        cache_read_tokens=categories.cache_read_tokens,
        cache_write_tokens=categories.cache_write_tokens,
        consumption_tokens=totals.consumption_tokens,
        usage_status=status,
        cache_overlap=totals.cache_overlap,
        reasoning_overlap=totals.reasoning_overlap,
        raw_usage=dict(raw_usage or {}),
    )
