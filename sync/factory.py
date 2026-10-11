"""Building a sync service for a collector.

The service's tuning (how far back an incremental scan re-reads) is configuration, so
routes construct it here rather than duplicating the wiring at each call site.
"""

import logging

from collectors.base import BaseCollector
from config.settings import Settings
from sync.service import SyncService

logger = logging.getLogger(__name__)


def build_sync_service(collector: BaseCollector, settings: Settings) -> SyncService:
    """Return a sync service for this collector, configured from settings."""
    logger.debug(
        "building sync service for %s with a %dms rescan overlap",
        collector.platform,
        settings.rescan_overlap_ms,
    )
    return SyncService(collector, rescan_overlap_ms=settings.rescan_overlap_ms)


__all__ = ["build_sync_service"]
