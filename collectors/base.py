"""Collector interface that every platform integration implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from schemas.usage import DiscoveryResult, UsageRecord


@dataclass(frozen=True)
class ScanOutcome:
    """Everything one collection pass found, including work that is not ready yet.

    `pending_timestamps_ms` carries the creation times of messages that exist upstream
    but are still generating. A caller storing these results must not advance its
    checkpoint past them, or the usage that lands when they finish would be skipped.
    """

    records: list[UsageRecord] = field(default_factory=list)
    pending_timestamps_ms: list[int] = field(default_factory=list)

    @property
    def latest_timestamp_ms(self) -> int | None:
        """Newest record's timestamp in epoch milliseconds, or None when empty."""
        if not self.records:
            return None
        return max(int(record.timestamp.timestamp() * 1000) for record in self.records)


class BaseCollector(ABC):
    """Read-only source of usage records for one platform (OpenCode first)."""

    @property
    @abstractmethod
    def platform(self) -> str:
        """Platform identifier stored on every record this collector emits."""

    @abstractmethod
    def discover(self) -> DiscoveryResult:
        """Locate the platform's local data; report 'not installed' instead of raising."""

    @abstractmethod
    def collect_history(self) -> list[UsageRecord]:
        """Return every usage record available so far; empty list when there are none."""

    @abstractmethod
    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        """Return usage records newer than the checkpoint; empty list when there are none."""

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        """Collect records and report anything still generating alongside them.

        The default implementation defers to `collect_updates`, which cannot see
        unfinished messages; collectors that can detect them override this.
        """
        return ScanOutcome(records=self.collect_updates(checkpoint))

    def refresh(self) -> None:
        """Discard anything cached about where this platform stores its data.

        Called before a manual rescan. A collector that caches source discovery
        overrides this, so the user who presses rescan because the numbers look
        wrong gets a genuine second look rather than the same cached answer.
        Collectors with nothing cached need do nothing.
        """
        return None
