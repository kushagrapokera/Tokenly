"""ORM models for usage events and collector state.

`usage_events` is the tracker's own record of what was used. It is deliberately
independent of OpenCode's storage: rows live here forever, so deleting an OpenCode
session file never removes usage that already happened.

The unique constraint on `(platform, source_event_id)` is what makes repeated scans
safe. `source_event_id` is OpenCode's `message.id`, which is stable across scans, so
re-collecting a message updates the existing row instead of double counting it.
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base
from database.types import UtcDateTime

USAGE_STATUS_VALUES = ("reported", "estimated", "unavailable")
COLLECTOR_STATUS_VALUES = ("idle", "scanning", "error")


def utc_now() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


class UsageEvent(Base):
    """One normalized model call, stored once and updated in place."""

    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint(
            "platform", "source_event_id", name="uq_usage_events_platform_source_event"
        ),
        CheckConstraint(
            "usage_status IN ('reported', 'estimated', 'unavailable')",
            name="ck_usage_events_usage_status",
        ),
        CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0)"
            " AND (output_tokens IS NULL OR output_tokens >= 0)"
            " AND (total_tokens IS NULL OR total_tokens >= 0)",
            name="ck_usage_events_non_negative_tokens",
        ),
        Index("ix_usage_events_timestamp", "timestamp"),
        Index("ix_usage_events_provider_id", "provider_id"),
        Index("ix_usage_events_model_id", "model_id"),
        Index("ix_usage_events_platform_timestamp", "platform", "timestamp"),
        Index("ix_usage_events_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    provider_id: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[str] = mapped_column(String, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumption_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_status: Mapped[str] = mapped_column(String, nullable=False, default="reported")

    cache_overlap: Mapped[str] = mapped_column(String, nullable=False, default="additive")
    reasoning_overlap: Mapped[str] = mapped_column(String, nullable=False, default="additive")

    raw_usage: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, default=utc_now, onupdate=utc_now
    )


class CollectorState(Base):
    """Where each collector got to, so the next scan resumes instead of restarting."""

    __tablename__ = "collector_state"
    __table_args__ = (
        UniqueConstraint("platform", name="uq_collector_state_platform"),
        CheckConstraint(
            "status IN ('idle', 'scanning', 'error')",
            name="ck_collector_state_status",
        ),
        Index("ix_collector_state_last_scan_at", "last_scan_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    checkpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="idle")
