"""Read-only collector for Codex CLI usage records.

Boundary adapter (Clean Code ch08): everything specific to Codex's rollout JSONL
layout and its three usage scopes is confined to `locator`, `reader`, and
`extractor`. This class exposes only the normalized `UsageRecord` contract.

Guarantees, per Phase 6 (`docs/codex_storage_analysis.md` §12):

  * never modifies Codex's source data (rollout files are only ever read)
  * never reads or stores API keys (only token/model/time fields are extracted)
  * never requires a network call or model pricing (pure local file reads)
  * never assumes complete usage metadata (missing usage becomes `unavailable`,
    not zero)
  * never ingests session or turn rollups (`turn_token_usage` and
    `thread_token_usage` equal the per-call sums — reading both would double
    every figure)
"""

import logging
from collections.abc import Callable, Iterator

from collectors.base import BaseCollector, ScanOutcome
from collectors.checkpoint import Checkpoint
from collectors.codex.extractor import PLATFORM, extract_usage_record
from collectors.codex.locator import resolve_sessions_directory
from collectors.codex.reader import (
    CodexUsageEvent,
    iter_usage_events,
    list_rollout_files,
)
from config.settings import Settings, get_settings
from errors.exceptions import CollectorSourceUnreadableError
from schemas.usage import DiscoveryResult, UsageRecord

logger = logging.getLogger(__name__)

STORAGE_FORMAT = "jsonl-rollout"

RecordExtractor = Callable[[CodexUsageEvent], UsageRecord | None]


class CodexCollector(BaseCollector):
    """Collects usage records from Codex CLI's local rollout session files."""

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
        """Report whether Codex data is readable here; never raise for 'not installed'."""
        sessions_directory = resolve_sessions_directory(self._settings)

        if not sessions_directory.is_dir():
            logger.info("no codex sessions directory at %s", sessions_directory)
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(sessions_directory),
                storage_format=STORAGE_FORMAT,
                detail="no Codex sessions directory at the resolved path",
            )

        rollout_files = list_rollout_files(sessions_directory)
        if not rollout_files:
            logger.info("no codex rollout files under %s", sessions_directory)
            return DiscoveryResult(
                platform=self.platform,
                available=False,
                source_path=str(sessions_directory),
                storage_format=STORAGE_FORMAT,
                detail="no rollout session files under the sessions directory",
            )

        logger.info(
            "found %d codex rollout file(s) under %s", len(rollout_files), sessions_directory
        )
        return DiscoveryResult(
            platform=self.platform,
            available=True,
            source_path=str(sessions_directory),
            storage_format=STORAGE_FORMAT,
            detail=f"{len(rollout_files)} rollout session files",
        )

    def collect_history(self) -> list[UsageRecord]:
        """Return every usage record available so far."""
        return list(self._iter_records(checkpoint=None))

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        """Return usage records newer than the checkpoint; empty list when there are none."""
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is not None:
            logger.info("collecting codex updates since %s", resume_from.to_datetime())
        return list(self._iter_records(checkpoint=resume_from))

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        """Collect records; Codex usage events arrive complete so nothing stays pending.

        Each `token_usage_record` is written when its call finishes and already
        carries the full per-call usage, so there is no in-flight work — the
        pending list is empty and the checkpoint may advance past everything seen.
        """
        resume_from = Checkpoint.parse(checkpoint)
        if resume_from is not None:
            logger.info("scanning codex since %s", resume_from.to_datetime())
        records = list(self._iter_records(checkpoint=resume_from))
        return ScanOutcome(records=records, pending_timestamps_ms=[])

    def _iter_records(self, checkpoint: Checkpoint | None) -> Iterator[UsageRecord]:
        """Yield normalized records across rollout files, optionally resuming."""
        sessions_directory = resolve_sessions_directory(self._settings)
        if not sessions_directory.is_dir():
            raise CollectorSourceUnreadableError(
                str(sessions_directory),
                FileNotFoundError("no Codex sessions directory at this path"),
            )

        collapsed: dict[str, UsageRecord] = {}
        duplicates = 0
        for rollout in list_rollout_files(sessions_directory):
            for event in iter_usage_events(rollout):
                timestamp_ms = _event_timestamp_ms(event)
                if (
                    checkpoint is not None
                    and timestamp_ms is not None
                    and checkpoint.covers(timestamp_ms)
                ):
                    continue
                try:
                    record = self._extract(event)
                except Exception as error:  # noqa: BLE001 - one bad event must not abort a scan
                    logger.warning(
                        "skipping codex usage event %s in %s: %s",
                        event.response_id,
                        rollout.name,
                        error,
                    )
                    continue
                if record is None:
                    continue
                if record.source_event_id in collapsed:
                    duplicates += 1
                    continue
                collapsed[record.source_event_id] = record

        if duplicates:
            logger.debug("collapsed %d repeated codex usage events", duplicates)
        return list(collapsed.values())


def _event_timestamp_ms(event: CodexUsageEvent) -> int | None:
    """Return the event's timestamp in epoch milliseconds, or None when missing."""
    if event.timestamp is None:
        return None
    return int(event.timestamp.timestamp() * 1000)
