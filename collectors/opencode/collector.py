"""Read-only collector for OpenCode usage records.

Boundary adapter (Clean Code ch08): everything specific to OpenCode's SQLite schema and
its `message.data` JSON shape is confined to `locator`, `snapshot`, `reader`, and
`extractor`. This class exposes only the normalized `UsageRecord` contract, so callers
never see OpenCode's storage details.

Guarantees, per the Phase 3 requirements:
  * never modifies OpenCode's source data (opened `mode=ro`, read via a temp snapshot)
  * never reads or stores API keys (only token/model/time fields are extracted)
  * never requires an API proxy or model pricing (pure local file reads)
  * never assumes complete usage metadata (missing usage becomes `unavailable`, not zero)
"""

import logging
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from collectors.base import BaseCollector, ScanOutcome
from collectors.checkpoint import Checkpoint
from collectors.opencode.extractor import PLATFORM, extract_usage_record
from collectors.opencode.locator import DataDirectoryResolver
from collectors.opencode.reader import (
    MessageRow,
    count_assistant_messages,
    iter_assistant_messages,
    list_sessions,
    open_snapshot,
)
from collectors.opencode.snapshot import SnapshotCache
from config.settings import Settings, get_settings
from errors.exceptions import CollectorError
from schemas.usage import DiscoveryResult, UsageRecord

logger = logging.getLogger(__name__)

STORAGE_FORMAT = "sqlite"

RecordExtractor = Callable[[MessageRow], UsageRecord | None]


class OpenCodeCollector(BaseCollector):
    """Collects usage records from the local OpenCode SQLite database."""

    def __init__(
        self,
        settings: Settings | None = None,
        record_extractor: RecordExtractor = extract_usage_record,
    ) -> None:
        self._settings = settings or get_settings()
        self._extract = record_extractor
        # Long-lived, so the data directory is resolved once rather than re-asked
        # from the CLI on every scan (~600 ms each time).
        self._resolver = DataDirectoryResolver(self._settings)
        # Reused between scans while the database is unchanged, which avoids copying
        # the whole file (~172 ms) on every pass.
        self._snapshots = SnapshotCache()

    @property
    def platform(self) -> str:
        return PLATFORM

    def refresh(self) -> None:
        """Discard cached source discovery so the next scan asks OpenCode again."""
        self._resolver.invalidate()
        self._snapshots.close()

    def discover(self) -> DiscoveryResult:
        """Report whether OpenCode data is readable here; never raise for 'not installed'."""
        database_path = self._resolver.database_path()

        if not database_path.is_file():
            logger.info("no opencode database at %s", database_path)
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(database_path),
                storage_format=STORAGE_FORMAT,
                detail="no OpenCode database file at the resolved path",
            )

        try:
            with self._snapshot_connection(database_path) as connection:
                sessions = len(list_sessions(connection))
                messages = count_assistant_messages(connection)
        except CollectorError as error:
            logger.warning("could not read the opencode database: %s", error)
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(database_path),
                storage_format=STORAGE_FORMAT,
                detail=str(error),
            )

        return DiscoveryResult(
            platform=self.platform,
            available=True,
            source_path=str(database_path),
            storage_format=STORAGE_FORMAT,
            detail=f"{sessions} sessions, {messages} assistant messages",
        )

    def collect_history(self) -> list[UsageRecord]:
        """Return every completed usage record OpenCode has stored."""
        logger.info("collecting full opencode history")
        return list(self._iter_records(checkpoint=None))

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        """Return records added since the checkpoint.

        Rows at the checkpoint's own millisecond are re-read: a message written at that
        instant may have been still generating last scan and now carry its usage.
        Records are keyed by `message.id`, so re-reading one is harmless.
        """
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is None:
            logger.info("no checkpoint given; collecting opencode updates from the beginning")
        else:
            logger.info("collecting opencode updates since %s", resume_from.to_datetime())
        return list(self._iter_records(checkpoint=resume_from))

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        """Collect completed records and report which messages are still generating.

        OpenCode writes a message row when generation starts and fills in its tokens when
        it finishes. Reporting those rows lets a caller hold its checkpoint back instead
        of stepping over usage that has not landed yet.
        """
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is not None:
            logger.info("scanning opencode since %s", resume_from.to_datetime())

        records: list[UsageRecord] = []
        pending: list[int] = []
        database_path = self._resolver.require_database_path()
        with self._snapshot_connection(database_path) as connection:
            for row in iter_assistant_messages(connection):
                if resume_from is not None and resume_from.covers(row.time_created_ms):
                    continue
                record = self._extract(row)
                if record is None:
                    pending.append(row.time_created_ms)
                    continue
                records.append(record)

        if pending:
            logger.debug("%d opencode messages are still generating", len(pending))
        return ScanOutcome(records=records, pending_timestamps_ms=pending)

    @contextmanager
    def _snapshot_connection(self, database_path: Path) -> Iterator[sqlite3.Connection]:
        """Yield a verified read-only connection to a private copy of the database."""
        with self._snapshots.snapshot(database_path) as snapshot_path:
            connection = open_snapshot(snapshot_path)
            try:
                yield connection
            finally:
                connection.close()

    def _iter_records(self, checkpoint: Checkpoint | None) -> Iterator[UsageRecord]:
        """Yield usage records from a fresh snapshot, optionally resuming from a checkpoint."""
        database_path = self._resolver.require_database_path()
        with self._snapshot_connection(database_path) as connection:
            for row in iter_assistant_messages(connection):
                if checkpoint is not None and checkpoint.covers(row.time_created_ms):
                    continue
                record = self._extract(row)
                if record is None:
                    continue
                yield record
