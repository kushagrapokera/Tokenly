"""Running every registered collector, one platform at a time.

`SyncService` handles a single collector and already records its own failures.
This module is the layer above it: the thing that decides which platforms get
scanned at all, and what happens when one of them cannot be scanned this time.

Two rules matter, and both come from the fact that platforms are independent of
each other:

1. **A platform that is not installed is not a failure.** Discovery reports it,
   the coordinator skips it, and the next run tries again. OpenCode or Cline
   simply being absent is a normal state, not something to mark as an error.

2. **One platform failing never stops another.** A broken Cline store must not
   cost the user their OpenCode history, so every collector is run inside its own
   session and its own try/except. A failure is reported as a failed result and
   the loop continues.
"""

import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collectors.base import BaseCollector
from config.settings import Settings
from sync.factory import build_sync_service
from sync.result import SyncResult
from sync.service import MODE_INCREMENTAL

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


class SyncCoordinator:
    """Scans every registered collector, isolating each from the others."""

    def __init__(
        self,
        collectors: Sequence[BaseCollector],
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._collectors = collectors
        self._settings = settings
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def platforms(self) -> list[str]:
        """The platforms this coordinator knows how to scan."""
        return [collector.platform for collector in self._collectors]

    def run_all(
        self,
        session_factory: SessionFactory,
        *,
        from_scratch: bool = False,
    ) -> list[SyncResult]:
        """Scan every available collector once and report what each one did.

        A platform whose data cannot be read is still reported, as a failed
        result, so the caller can see it rather than wondering why it is missing.
        """
        results = [
            self._run_one(collector, session_factory, from_scratch=from_scratch)
            for collector in self._collectors
        ]
        self._log_summary(results)
        return results

    def _run_one(
        self,
        collector: BaseCollector,
        session_factory: SessionFactory,
        *,
        from_scratch: bool,
    ) -> SyncResult:
        """Scan one collector, never raising and never touching the others."""
        platform = collector.platform
        if not self._is_available(collector):
            logger.info("skipping %s: its data is not present on this machine", platform)
            return self._skipped(platform)

        try:
            with session_factory() as session:
                return build_sync_service(collector, self._settings).run(
                    session, from_scratch=from_scratch
                )
        except Exception as error:  # noqa: BLE001 - one platform must not stop the rest
            logger.exception("could not run %s; other platforms continue", platform)
            return self._failed(platform, error)

    def _is_available(self, collector: BaseCollector) -> bool:
        """Report whether this collector has something to read."""
        try:
            discovery = collector.discover()
        except Exception:  # noqa: BLE001 - discovery problems are this platform's alone
            logger.exception(
                "could not discover %s; treating it as unavailable", collector.platform
            )
            return False
        if not discovery.available:
            logger.info("%s is not available: %s", collector.platform, discovery.detail)
        return discovery.available

    def _skipped(self, platform: str) -> SyncResult:
        """Return a result for a platform that was never scanned."""
        now = self._clock()
        return SyncResult(
            platform=platform,
            mode=MODE_INCREMENTAL,
            scanned=0,
            inserted=0,
            updated=0,
            skipped_in_flight=0,
            checkpoint=None,
            started_at=now,
            finished_at=now,
        )

    def _failed(self, platform: str, error: Exception) -> SyncResult:
        """Return a result describing a failure that happened outside SyncService."""
        now = self._clock()
        return SyncResult(
            platform=platform,
            mode=MODE_INCREMENTAL,
            scanned=0,
            inserted=0,
            updated=0,
            skipped_in_flight=0,
            checkpoint=None,
            started_at=now,
            finished_at=now,
            failed=True,
            error_message=str(error),
        )

    def _log_summary(self, results: Sequence[SyncResult]) -> None:
        """Log one line describing the whole pass, whatever each platform did."""
        for result in results:
            if result.failed:
                logger.warning(
                    "%s failed after scanning %d record(s): %s",
                    result.platform,
                    result.scanned,
                    result.error_message,
                )
                continue
            logger.info(
                "%s scanned %d record(s), stored %d",
                result.platform,
                result.scanned,
                result.stored,
            )


def build_sync_coordinator(
    collectors: Sequence[BaseCollector],
    settings: Settings,
) -> SyncCoordinator:
    """Return a coordinator for the collectors this application was built with."""
    platforms = [collector.platform for collector in collectors]
    logger.debug("coordinating %d collector(s): %s", len(collectors), platforms)
    return SyncCoordinator(collectors, settings)


__all__ = ["SyncCoordinator", "build_sync_coordinator"]