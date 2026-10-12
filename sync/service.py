"""Drive a collector into the database, exactly once per usage event.

The whole point of this module is that repeated runs must not inflate totals. Three
rules get that right, and each is enforced in code rather than left to convention:

1. **The checkpoint only advances after the records are committed.** A crash between
   storing records and saving progress leaves a stale checkpoint, so the next scan
   re-reads a window it has already seen. Re-reading is harmless because writes are
   idempotent. The reverse, advancing first, would silently skip usage forever.

2. **A message still generating holds the checkpoint back.** OpenCode writes a message
   when generation *starts* and fills in its tokens when it finishes. Advancing past an
   unfinished message would skip it permanently, so the checkpoint is capped at the
   oldest message still in flight.

3. **Nothing is ever deleted.** Session compaction and retries can remove rows from
   OpenCode's database; usage that already happened stays in ours.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collectors.base import BaseCollector, ScanOutcome
from collectors.checkpoint import Checkpoint
from database.repository import upsert_usage_records
from database.state import (
    CollectorProgress,
    load_progress,
    mark_error,
    mark_scanning,
    save_progress,
)
from sync.result import SyncResult

logger = logging.getLogger(__name__)

MODE_HISTORICAL = "historical"
MODE_INCREMENTAL = "incremental"


class SyncService:
    """Runs a collector and stores its output without ever double counting."""

    def __init__(
        self,
        collector: BaseCollector,
        rescan_overlap_ms: int = 0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._collector = collector
        self._rescan_overlap_ms = rescan_overlap_ms
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def run(self, session: Session, *, from_scratch: bool = False) -> SyncResult:
        """Perform one synchronization pass and store whatever it finds.

        `from_scratch` ignores the stored checkpoint and reads the whole source, which
        is what a manual rescan means. It is safe: the upsert is idempotent, so a full
        re-read updates rows in place instead of doubling the totals. The checkpoint is
        still advanced afterwards, so the next ordinary scan resumes normally.
        """
        platform = self._collector.platform
        started_at = self._clock()
        progress = load_progress(session, platform)
        previous_checkpoint = progress.checkpoint if progress else None
        source_path = progress.source_path if progress else ""

        self._warn_if_interrupted(platform, progress)

        if from_scratch:
            logger.info(
                "running a full rescan for %s; ignoring checkpoint %s",
                platform,
                previous_checkpoint,
            )
            previous_checkpoint = None

        mode = MODE_HISTORICAL if previous_checkpoint is None else MODE_INCREMENTAL
        resume_from = self._resume_point(previous_checkpoint)

        mark_scanning(session, platform, source_path)
        logger.info("starting %s scan for %s", mode, platform)

        try:
            outcome = self._collector.collect_scan(resume_from)
            written = upsert_usage_records(session, outcome.records, now=started_at)
        except Exception as error:  # noqa: BLE001 - recorded, reported, never swallowed
            mark_error(session, platform, source_path)
            logger.exception("sync failed for %s; checkpoint left unchanged", platform)
            return SyncResult(
                platform=platform,
                mode=mode,
                scanned=0,
                inserted=0,
                updated=0,
                skipped_in_flight=0,
                checkpoint=previous_checkpoint,
                started_at=started_at,
                finished_at=self._clock(),
                failed=True,
                error_message=str(error),
            )

        checkpoint = self._next_checkpoint(previous_checkpoint, outcome)
        save_progress(
            session,
            platform,
            source_path=source_path,
            checkpoint=checkpoint,
            status="idle",
            scanned_at=self._clock(),
        )
        logger.info(
            "%s scan stored %d new and %d existing records for %s",
            mode,
            written.inserted,
            written.updated,
            platform,
        )

        return SyncResult(
            platform=platform,
            mode=mode,
            scanned=len(outcome.records),
            inserted=written.inserted,
            updated=written.updated,
            skipped_in_flight=len(outcome.pending_timestamps_ms),
            checkpoint=checkpoint,
            started_at=started_at,
            finished_at=self._clock(),
        )

    def _warn_if_interrupted(self, platform: str, progress: CollectorProgress | None) -> None:
        """Log when the previous run never finished, so the retry is explainable."""
        if progress is None or progress.status != "scanning":
            return
        logger.warning(
            "collector %s was still marked scanning at %s, so its last run did not "
            "finish; resuming from checkpoint %s",
            platform,
            progress.last_scan_at,
            progress.checkpoint,
        )

    def _resume_point(self, checkpoint: str | None) -> str | None:
        """Return the checkpoint to resume from, pulled back by the rescan overlap.

        Re-reading a little extra costs a few redundant upserts and buys recovery from a
        message that finished generating after the previous scan passed over it.
        """
        parsed = Checkpoint.parse(checkpoint)
        if parsed is None or self._rescan_overlap_ms <= 0:
            return checkpoint
        overlapped = Checkpoint(last_seen_ms=parsed.last_seen_ms - self._rescan_overlap_ms)
        return overlapped.serialize()

    def _next_checkpoint(self, previous: str | None, outcome: ScanOutcome) -> str | None:
        """Work out where the next scan should resume from.

        The checkpoint never moves past the oldest message still generating, and never
        moves backwards, so a scan that found nothing keeps the position it had.
        """
        latest = outcome.latest_timestamp_ms
        if latest is None:
            return previous

        if outcome.pending_timestamps_ms:
            oldest_pending = min(outcome.pending_timestamps_ms)
            if oldest_pending < latest:
                logger.debug(
                    "holding checkpoint at %s: a message from that moment is still generating",
                    oldest_pending,
                )
                return str(oldest_pending - 1)

        return str(latest)
