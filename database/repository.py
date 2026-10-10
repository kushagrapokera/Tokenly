"""Storing and retrieving normalized usage records.

The one behaviour that matters here is idempotency. A collector can hand us the same
message repeatedly — a rescan, a restart, a re-read of the checkpoint's millisecond — and
storing it twice would inflate every total. So writes go through `upsert_usage_records`,
which matches on `(platform, source_event_id)` and updates in place.

Nothing here deletes a usage row. Rows outlive the OpenCode session they came from: usage
that happened is history, and deleting a session file must not rewrite the past.
"""

import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from database.models import UsageEvent
from schemas.usage import UsageRecord

logger = logging.getLogger(__name__)

# Columns an incoming record may refresh. created_at is deliberately absent: it records
# when the event was first imported and must not move on a later update.
UPDATABLE_COLUMNS = (
    "provider_id",
    "model_id",
    "session_id",
    "message_id",
    "timestamp",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "reasoning_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "consumption_tokens",
    "usage_status",
    "cache_overlap",
    "reasoning_overlap",
    "raw_usage",
    "updated_at",
)


@dataclass(frozen=True)
class UpsertResult:
    """What an upsert did, so callers can log or react without re-querying."""

    inserted: int
    updated: int

    @property
    def total(self) -> int:
        return self.inserted + self.updated


def upsert_usage_records(
    session: Session, records: Iterable[UsageRecord], *, now: datetime | None = None
) -> UpsertResult:
    """Insert new records and update existing ones, keyed by platform and source event id.

    An empty batch is a no-op rather than an error, so a collector that found nothing
    this scan does not have to special-case it.
    """
    batch = list(records)
    if not batch:
        logger.debug("no usage records to upsert")
        return UpsertResult(inserted=0, updated=0)

    timestamp = now or datetime.now(timezone.utc)
    inserted, updated = _split_existing(session, batch, timestamp)

    for row in inserted:
        session.add(row)
    for values in updated:
        session.execute(_update_statement(values))

    session.commit()
    logger.info("upserted %d new and %d existing usage records", len(inserted), len(updated))
    return UpsertResult(inserted=len(inserted), updated=len(updated))


def count_usage_events(session: Session, platform: str | None = None) -> int:
    """Return how many usage events are stored, optionally for one platform."""
    statement = select(func.count()).select_from(UsageEvent)
    if platform is not None:
        statement = statement.where(UsageEvent.platform == platform)
    return int(session.execute(statement).scalar_one())


def query_usage_events(
    session: Session,
    *,
    platform: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    provider_id: str | None = None,
    model_id: str | None = None,
    limit: int | None = None,
) -> Sequence[UsageEvent]:
    """Return stored events, oldest first, filtered by the common query dimensions.

    Every filter here maps to an index declared in `database.models`, which is what
    keeps date-range aggregation fast as the table grows.
    """
    statement = select(UsageEvent)
    if platform is not None:
        statement = statement.where(UsageEvent.platform == platform)
    if start is not None:
        statement = statement.where(UsageEvent.timestamp >= start)
    if end is not None:
        statement = statement.where(UsageEvent.timestamp < end)
    if provider_id is not None:
        statement = statement.where(UsageEvent.provider_id == provider_id)
    if model_id is not None:
        statement = statement.where(UsageEvent.model_id == model_id)

    statement = statement.order_by(UsageEvent.timestamp, UsageEvent.id)
    if limit is not None:
        statement = statement.limit(limit)
    return session.execute(statement).scalars().all()


_SUMMABLE_COLUMNS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "reasoning_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "consumption_tokens",
)


def sum_tokens(
    session: Session,
    column: str,
    *,
    platform: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """Sum one token column over a filtered range, treating unknown counts as zero.

    Aggregation belongs to Phase 7; this exists so the repository can answer the
    simplest question now and be the single place range filtering is defined.
    """
    if column not in _SUMMABLE_COLUMNS:
        raise ValueError(f"{column!r} is not a summable token column")

    statement = select(func.coalesce(func.sum(getattr(UsageEvent, column)), 0))
    if platform is not None:
        statement = statement.where(UsageEvent.platform == platform)
    if start is not None:
        statement = statement.where(UsageEvent.timestamp >= start)
    if end is not None:
        statement = statement.where(UsageEvent.timestamp < end)
    return int(session.execute(statement).scalar_one())


def _split_existing(
    session: Session, records: list[UsageRecord], now: datetime
) -> tuple[list[UsageEvent], list[dict[str, Any]]]:
    """Split a batch into rows to insert and value dicts to update."""
    keys = [(record.platform, record.source_event_id) for record in records]
    existing = _existing_keys(session, keys)
    return _build_inserts(records, existing, now), _build_updates(records, existing, now)


def _existing_keys(session: Session, keys: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """Return which (platform, source_event_id) pairs are already stored."""
    platforms = {platform for platform, _ in keys}
    statement = select(UsageEvent.platform, UsageEvent.source_event_id).where(
        UsageEvent.platform.in_(platforms)
    )
    stored = {(row[0], row[1]) for row in session.execute(statement)}
    return stored & set(keys)


def _build_inserts(
    records: list[UsageRecord], existing: set[tuple[str, str]], now: datetime
) -> list[UsageEvent]:
    """Build ORM rows for records not yet stored."""
    return [
        _to_model(record, now)
        for record in records
        if (record.platform, record.source_event_id) not in existing
    ]


def _build_updates(
    records: list[UsageRecord], existing: set[tuple[str, str]], now: datetime
) -> list[dict[str, Any]]:
    """Build value dicts for records already stored."""
    updates: list[dict[str, Any]] = []
    for record in records:
        if (record.platform, record.source_event_id) not in existing:
            continue
        values = _to_values(record, now)
        values["platform"] = record.platform
        values["source_event_id"] = record.source_event_id
        updates.append(values)
    return updates


def _update_statement(values: dict[str, Any]) -> Any:
    """Build the UPDATE that refreshes one already-stored record."""
    statement = (
        sqlite_insert(UsageEvent)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[UsageEvent.platform, UsageEvent.source_event_id],
            set_={column: values[column] for column in UPDATABLE_COLUMNS},
        )
    )
    return statement


def _to_model(record: UsageRecord, now: datetime) -> UsageEvent:
    """Turn a usage record into an ORM row."""
    values = _to_values(record, now)
    values["created_at"] = now
    return UsageEvent(**values)


def _to_values(record: UsageRecord, now: datetime) -> dict[str, Any]:
    """Map a usage record onto the model's columns."""
    return {
        "platform": record.platform,
        "provider_id": record.provider_id,
        "model_id": record.model_id,
        "session_id": record.session_id,
        "message_id": record.message_id,
        "source_event_id": record.source_event_id,
        "timestamp": record.timestamp,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "total_tokens": record.total_tokens,
        "reasoning_tokens": record.reasoning_tokens,
        "cache_read_tokens": record.cache_read_tokens,
        "cache_write_tokens": record.cache_write_tokens,
        "consumption_tokens": record.consumption_tokens,
        "usage_status": record.usage_status,
        "cache_overlap": record.cache_overlap,
        "reasoning_overlap": record.reasoning_overlap,
        "raw_usage": json.dumps(record.raw_usage, default=str),
        "updated_at": now,
    }
