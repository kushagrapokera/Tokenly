"""What a synchronization run did.

These types exist so callers can report on a scan without reaching into the database,
and so tests can assert on behaviour rather than on row counts.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SyncResult:
    """The outcome of one synchronization run."""

    platform: str
    mode: str
    scanned: int
    inserted: int
    updated: int
    skipped_in_flight: int
    checkpoint: str | None
    started_at: datetime
    finished_at: datetime
    source_path: str = ""
    failed: bool = False
    error_message: str = ""

    @property
    def stored(self) -> int:
        """Records written to the database this run, inserted plus updated."""
        return self.inserted + self.updated

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def succeeded(self) -> bool:
        return not self.failed
