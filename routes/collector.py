"""Collector endpoints: tracking status and manual rescans.

Status answers "is collection working and where is it up to", which is what the
dashboard's tracking panel displays. Rescan answers "go and read the source now",
which is the recovery path when a session was compacted or a scan failed.

Both read the same stored progress the sync loop writes, so the panel reflects reality
rather than a separate bookkeeping trail.
"""

import logging
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from collectors.base import BaseCollector
from config.settings import Settings
from database.repository import count_usage_events
from database.state import load_progress
from errors.exceptions import NotFoundError
from routes.dependencies import PlatformPath, SessionDependency, SettingsDependency
from schemas.collector import CollectorListResponse, CollectorStatusResponse, RescanResponse
from sync import build_sync_service
from sync.result import SyncResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collector", tags=["collector"])


def get_collectors(request: Request) -> Sequence[BaseCollector]:
    """Return the collectors this application was built with."""
    collectors: Sequence[BaseCollector] = request.app.state.collectors
    return collectors


CollectorsDependency = Annotated[Sequence[BaseCollector], Depends(get_collectors)]


@router.get("/status", response_model=CollectorListResponse)
def read_collector_status(
    session: SessionDependency,
    collectors: CollectorsDependency,
) -> CollectorListResponse:
    """Report every collector's availability, last scan, and stored event count.

    Discovery failures are reported as `available: false` with the reason, never as an
    error response: an absent OpenCode installation is a normal state for this panel.
    """
    statuses = [_status_for(session, collector) for collector in collectors]
    return CollectorListResponse(collectors=statuses)


@router.get("/status/{platform}", response_model=CollectorStatusResponse)
def read_platform_status(
    platform: PlatformPath,
    session: SessionDependency,
    collectors: CollectorsDependency,
) -> CollectorStatusResponse:
    """Report one collector's status; 404 when no such platform is registered."""
    collector = _find_collector(collectors, platform)
    return _status_for(session, collector)


@router.post("/rescan", response_model=list[RescanResponse])
def trigger_rescan(
    session: SessionDependency,
    settings: SettingsDependency,
    collectors: CollectorsDependency,
) -> list[RescanResponse]:
    """Run a full rescan for every collector and report what each one did.

    A failed scan is reported with `succeeded: false` and its reason rather than as an
    error response, because one platform failing should not hide what the others did.
    """
    results = [_run_rescan(session, collector, settings) for collector in collectors]
    logger.info("rescan finished for %d collector(s)", len(results))
    return [RescanResponse.from_result(result) for result in results]


@router.post("/rescan/{platform}", response_model=RescanResponse)
def trigger_platform_rescan(
    platform: PlatformPath,
    session: SessionDependency,
    settings: SettingsDependency,
    collectors: CollectorsDependency,
) -> RescanResponse:
    """Run a full rescan for one collector; 404 when no such platform is registered."""
    collector = _find_collector(collectors, platform)
    return RescanResponse.from_result(_run_rescan(session, collector, settings))


def _run_rescan(session: Session, collector: BaseCollector, settings: Settings) -> SyncResult:
    """Run one collector's full rescan and log its outcome.

    The collector is refreshed first: a rescan is what a user reaches for when the
    numbers look wrong, so it must not be answered from a cached view of where the
    source lives.
    """
    logger.info("rescan requested for %s", collector.platform)
    collector.refresh()
    return build_sync_service(collector, settings).run(session, from_scratch=True)


def _status_for(session: Session, collector: BaseCollector) -> CollectorStatusResponse:
    """Build one collector's status from discovery plus stored progress."""
    discovery = collector.discover()
    progress = load_progress(session, collector.platform)
    return CollectorStatusResponse.build(
        collector=collector,
        available=discovery.available,
        source_path=discovery.source_path,
        storage_format=discovery.storage_format,
        discovery_detail=discovery.detail,
        progress=progress,
        stored_events=count_usage_events(session, collector.platform),
    )


def _find_collector(collectors: Sequence[BaseCollector], platform: str) -> BaseCollector:
    """Return the named collector, or raise a 404 naming the platforms that exist."""
    for collector in collectors:
        if collector.platform == platform:
            return collector
    known = ", ".join(collector.platform for collector in collectors)
    logger.warning("no collector registered for platform %r", platform)
    raise NotFoundError(f"unknown platform {platform!r}; known platforms: {known}")


__all__ = ["router"]
