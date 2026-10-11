"""Response bodies for the collector endpoints.

The dashboard's tracking panel needs three things: whether OpenCode was found, when the
last sync happened, and how much was imported. They are reported together so the panel
never has to guess whether a missing number means "none" or "not collected yet".
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from collectors.base import BaseCollector
from database.state import CollectorProgress
from sync.result import SyncResult


def _now() -> datetime:
    """Return the response generation time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


class CollectorStatusResponse(BaseModel):
    """Whether one collector is usable, and where its last scan got to.

    `status` comes from the stored progress row. `never_scanned` means the collector
    exists and its source was readable, but no scan has been stored yet — different
    from `error`, which means a scan was attempted and failed.
    """

    platform: str
    available: bool
    status: str
    source_path: str
    storage_format: str
    detail: str = ""
    checkpoint: str | None = None
    last_scan_at: datetime | None = None
    stored_events: int = 0

    @classmethod
    def build(
        cls,
        collector: BaseCollector,
        discovery_detail: str,
        available: bool,
        source_path: str,
        storage_format: str,
        progress: CollectorProgress | None,
        stored_events: int,
    ) -> CollectorStatusResponse:
        """Combine discovery and stored progress into one status body."""
        return cls(
            platform=collector.platform,
            available=available,
            status=progress.status if progress else "never_scanned",
            source_path=source_path,
            storage_format=storage_format,
            detail=discovery_detail,
            checkpoint=progress.checkpoint if progress else None,
            last_scan_at=progress.last_scan_at if progress else None,
            stored_events=stored_events,
        )


class CollectorListResponse(BaseModel):
    """Every configured collector's status."""

    collectors: list[CollectorStatusResponse]
    generated_at: datetime = Field(default_factory=_now)


class RescanResponse(BaseModel):
    """What one triggered scan did.

    A scan that failed is still reported, with `succeeded` false and the reason, so the
    dashboard can show what went wrong instead of a bare failure.
    """

    platform: str
    mode: str
    succeeded: bool
    scanned: int
    inserted: int
    updated: int
    stored: int
    skipped_in_flight: int
    checkpoint: str | None = None
    duration_seconds: float
    started_at: datetime
    finished_at: datetime
    error_message: str = ""

    @classmethod
    def from_result(cls, result: SyncResult) -> RescanResponse:
        """Wrap one synchronization outcome in its response shape."""
        return cls(
            platform=result.platform,
            mode=result.mode,
            succeeded=result.succeeded,
            scanned=result.scanned,
            inserted=result.inserted,
            updated=result.updated,
            stored=result.stored,
            skipped_in_flight=result.skipped_in_flight,
            checkpoint=result.checkpoint,
            duration_seconds=result.duration_seconds,
            started_at=result.started_at,
            finished_at=result.finished_at,
            error_message=result.error_message,
        )


__all__ = ["CollectorListResponse", "CollectorStatusResponse", "RescanResponse"]
