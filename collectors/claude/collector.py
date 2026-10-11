"""Read-only collector for Claude Code usage records.

Boundary adapter (Clean Code ch08): everything specific to Claude Code's
JSONL transcript layout is confined to `locator`, `reader`, and `extractor`.
This class exposes only the normalized `UsageRecord` contract, so callers
never see Claude Code's storage details.

Guarantees, per the Phase 3 requirements:

  * never modifies Claude Code's source data (pure read-only file reads)
  * never reads or stores credentials (no settings/env values touched; only
    token/model/time fields are extracted)
  * never requires an API key, proxy, or pricing data (pure local reads)
  * never assumes complete usage metadata (missing usage becomes
    `unavailable`, not zero)

Claude Code writes one JSONL line per streamed content block of a model
request, repeating `message.id` and its usage. `extract_usage_records`
collapses those repeats by the namespaced `session:message` identity, so a
session's 165 lines become its 58 actual model requests.
"""

import logging
from collections.abc import Callable

from collectors.base import BaseCollector, ScanOutcome
from collectors.checkpoint import Checkpoint
from collectors.claude.extractor import PLATFORM, extract_usage_record
from collectors.claude.locator import resolve_projects_directory
from collectors.claude.reader import AssistantRecord, iter_assistant_records, list_session_files
from config.settings import Settings, get_settings
from errors.exceptions import CollectorSourceUnreadableError
from schemas.usage import DiscoveryResult, UsageRecord

logger = logging.getLogger(__name__)

STORAGE_FORMAT = "jsonl"

RecordExtractor = Callable[[AssistantRecord], UsageRecord | None]


class ClaudeCodeCollector(BaseCollector):
    """Collects usage records from Claude Code's local session transcripts."""

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
        """Report whether Claude Code data is readable here; never raise for 'not installed'."""
        projects_directory = resolve_projects_directory(self._settings)

        if not projects_directory.is_dir():
            logger.info("no claude projects directory at %s", projects_directory)
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(projects_directory),
                storage_format=STORAGE_FORMAT,
                detail="no Claude Code projects directory at the resolved path",
            )

        sessions = list_session_files(projects_directory)
        if not sessions:
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(projects_directory),
                storage_format=STORAGE_FORMAT,
                detail="no session transcripts under the projects directory",
            )

        return DiscoveryResult(
            platform=self.platform,
            available=True,
            source_path=str(projects_directory),
            storage_format=STORAGE_FORMAT,
            detail=f"{len(sessions)} session transcripts",
        )

    def collect_history(self) -> list[UsageRecord]:
        """Return every usage record Claude Code has stored."""
        logger.info("collecting full claude code history")
        return list(self._iter_records(checkpoint=None))

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        """Return records added since the checkpoint.

        Transcripts are append-only, so an older message's usage does not
        change after it is written; the checkpoint filter is a plain
        timestamp comparison. Records are keyed by
        `{session_id}:{message_id}`, so re-reading is harmless.
        """
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is None:
            logger.info("no checkpoint given; collecting claude code updates from the beginning")
        else:
            logger.info("collecting claude code updates since %s", resume_from.to_datetime())
        return list(self._iter_records(checkpoint=resume_from))

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        """Collect records; assistant lines arrive complete so nothing stays pending.

        Unlike OpenCode (rows written at generation start), a Claude Code
        line carries its usage when written. Lines without usage are
        `unavailable` records, not in-flight work — so the pending list is
        always empty and the checkpoint may advance past everything seen.
        """
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is not None:
            logger.info("scanning claude code since %s", resume_from.to_datetime())
        records = self._iter_records(checkpoint=resume_from)
        return ScanOutcome(records=records, pending_timestamps_ms=[])

    def _iter_records(self, checkpoint: Checkpoint | None) -> list[UsageRecord]:
        """Return one usage record per model request, optionally after a checkpoint.

        Collapse happens here, shared by history and incremental scans, so no
        entry point can count a request's repeated lines twice — the one rule
        without which every Claude Code total would inflate ~3x.
        """
        projects_directory = resolve_projects_directory(self._settings)
        if not projects_directory.is_dir():
            raise CollectorSourceUnreadableError(
                str(projects_directory),
                FileNotFoundError("no Claude Code projects directory at this path"),
            )
        collapsed: dict[str, UsageRecord] = {}
        duplicates = 0
        for session_file in list_session_files(projects_directory):
            for assistant in iter_assistant_records(session_file):
                if checkpoint is not None and _is_before_checkpoint(assistant, checkpoint):
                    continue
                try:
                    record = self._extract(assistant)
                except Exception as error:  # noqa: BLE001 - one bad line must not end the scan
                    logger.warning(
                        "skipping claude assistant line in %s: %s", session_file.session_id, error
                    )
                    continue
                if record is None:
                    continue
                if record.source_event_id in collapsed:
                    duplicates += 1
                    continue
                collapsed[record.source_event_id] = record
        if duplicates:
            logger.debug("collapsed %d repeated claude request lines", duplicates)
        return list(collapsed.values())


def _is_before_checkpoint(record: AssistantRecord, checkpoint: Checkpoint) -> bool:
    """Report whether a line's timestamp is already covered by the checkpoint."""
    stamp_ms = _record_ms(record)
    if stamp_ms is None:
        # A line with no timestamp cannot be dated, so it is never filtered.
        return False
    return checkpoint.covers(stamp_ms)


def _record_ms(record: AssistantRecord) -> int | None:
    """Return a record's timestamp in epoch milliseconds, or None."""
    if record.timestamp is None:
        return None
    return int(record.timestamp.timestamp() * 1000)
