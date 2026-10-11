"""Read-only collector for Cline CLI usage records.

Boundary adapter (Clean Code ch08): everything specific to Cline's session
index schema and its `.messages.json` shape is confined to `locator`,
`snapshot`, `reader`, and `extractor`. This class exposes only the normalized
`UsageRecord` contract, so callers never see Cline's storage details.

Guarantees, per the Phase 3 requirements:

  * never modifies Cline's source data (index opened `mode=ro` via a temp
    snapshot; message files only ever read)
  * never reads or stores API keys (`providers.json` is never opened; only
    token/model/time fields are extracted)
  * never requires an API proxy or model pricing (pure local file reads)
  * never assumes complete usage metadata (missing metrics becomes
    `unavailable`, not zero)
  * never ingests session rollups (`metadata.usage` equals the per-message
    sums — reading both would double every figure)
"""

import logging
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from collectors.base import BaseCollector, ScanOutcome
from collectors.checkpoint import Checkpoint
from collectors.cline.extractor import PLATFORM, MalformedMessageError, extract_usage_record
from collectors.cline.locator import (
    resolve_database_path,
    resolve_sessions_directory,
)
from collectors.cline.reader import (
    ASSISTANT_ROLE,
    MessageRow,
    iter_session_messages,
    list_sessions,
    open_session_index,
    session_ids_in_directory,
)
from collectors.cline.snapshot import snapshot_database
from config.settings import Settings, get_settings
from errors.exceptions import CollectorError, CollectorSourceUnreadableError
from schemas.usage import DiscoveryResult, UsageRecord

logger = logging.getLogger(__name__)

STORAGE_FORMAT = "json+sqlite-index"


RecordExtractor = Callable[[MessageRow], UsageRecord | None]


class ClineCollector(BaseCollector):
    """Collects usage records from Cline CLI's local session files."""

    def __init__(
        self,
        settings: Settings | None = None,
        record_extractor: RecordExtractor = extract_usage_record,
    ) -> None:
        self._settings = settings or get_settings()
        self._extract = record_extractor

    @property
    def platform(self) -> str:
        return PLATFORM

    def discover(self) -> DiscoveryResult:
        """Report whether Cline data is readable here; never raise for 'not installed'."""
        sessions_directory = resolve_sessions_directory(self._settings)
        database_path = resolve_database_path(self._settings)

        if not sessions_directory.is_dir():
            logger.info("no cline sessions directory at %s", sessions_directory)
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(sessions_directory),
                storage_format=STORAGE_FORMAT,
                detail="no Cline sessions directory at the resolved path",
            )

        try:
            session_count = len(self._session_ids())
            message_count = self._count_assistant_messages()
        except CollectorError as error:
            logger.warning("could not read the cline store: %s", error)
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(sessions_directory),
                storage_format=STORAGE_FORMAT,
                detail=str(error),
            )

        index_note = "session index present" if database_path.is_file() else "index absent"
        return DiscoveryResult(
            platform=self.platform,
            available=True,
            source_path=str(sessions_directory),
            storage_format=STORAGE_FORMAT,
            detail=f"{session_count} sessions, {message_count} assistant messages ({index_note})",
        )

    def collect_history(self) -> list[UsageRecord]:
        """Return every usage record Cline has stored."""
        logger.info("collecting full cline history")
        return list(self._iter_records(checkpoint=None))

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        """Return records added since the checkpoint.

        Rows at the checkpoint's own millisecond are re-read: a message file
        rewritten at that instant may have gained records since the last scan.
        Records are keyed by `{session_id}:{message_id}`, so re-reading is
        harmless.
        """
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is None:
            logger.info("no checkpoint given; collecting cline updates from the beginning")
        else:
            logger.info("collecting cline updates since %s", resume_from.to_datetime())
        return list(self._iter_records(checkpoint=resume_from))

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        """Collect records; Cline messages arrive complete so nothing stays pending.

        Unlike OpenCode (rows written at generation start), Cline message files
        carry full metrics when present. Messages without metrics are
        `unavailable` records, not in-flight work — so the pending list is
        always empty and the checkpoint may advance past everything seen.
        """
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is not None:
            logger.info("scanning cline since %s", resume_from.to_datetime())
        records = list(self._iter_records(checkpoint=resume_from))
        return ScanOutcome(records=records, pending_timestamps_ms=[])

    def _session_ids(self) -> list[str]:
        """Return the union of indexed sessions and on-disk session directories."""
        sessions_directory = resolve_sessions_directory(self._settings)
        database_path = resolve_database_path(self._settings)
        indexed: set[str] = set()
        if database_path.is_file():
            with self._snapshot_connection(database_path) as connection:
                indexed = {row.session_id for row in list_sessions(connection)}
        else:
            logger.info("no cline session index at %s; using session files only", database_path)
        on_disk = set(session_ids_in_directory(sessions_directory))
        return sorted(indexed | on_disk)

    def _count_assistant_messages(self) -> int:
        """Return how many assistant messages the store holds (for discovery detail)."""
        sessions_directory = resolve_sessions_directory(self._settings)
        count = 0
        for session_id in self._session_ids():
            for row in iter_session_messages(sessions_directory, session_id):
                if row.data.get("role") == ASSISTANT_ROLE:
                    count += 1
        return count

    @contextmanager
    def _snapshot_connection(self, database_path: Path) -> Iterator[sqlite3.Connection]:
        """Yield a verified read-only connection to a private copy of the index."""
        with snapshot_database(database_path) as snapshot_path:
            connection = open_session_index(snapshot_path)
            try:
                yield connection
            finally:
                connection.close()

    def _iter_records(self, checkpoint: Checkpoint | None) -> Iterator[UsageRecord]:
        """Yield usage records across sessions, optionally resuming from a checkpoint."""
        sessions_directory = resolve_sessions_directory(self._settings)
        if not sessions_directory.is_dir():
            raise CollectorSourceUnreadableError(
                str(sessions_directory),
                FileNotFoundError("no Cline sessions directory at this path"),
            )
        for session_id in self._session_ids():
            for row in iter_session_messages(sessions_directory, session_id):
                if checkpoint is not None and checkpoint.covers(row.time_created_ms):
                    continue
                try:
                    record = self._extract(row)
                except MalformedMessageError as error:
                    logger.warning("skipping malformed cline message: %s", error)
                    continue
                if record is None:
                    continue
                yield record
