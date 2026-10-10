"""Incremental scan checkpoints for collectors.

A checkpoint is the timestamp of the newest message a collector has already seen, so
the next scan only has to look at what came after it. Storing the timestamp rather
than the last id keeps the checkpoint small and lets a scan resume correctly even when
messages share an identical millisecond.

Two wrinkles the OpenCode storage imposes:

  * Messages are written when generation *starts*, so a scan can see a message whose
    usage is not there yet. Deferring it must not advance the checkpoint past it.
  * `time_created` is the row's creation time and never changes, so it is a stable
    resume point even if OpenCode later backfills a message's usage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from errors.exceptions import CollectorError


class InvalidCheckpointError(CollectorError):
    """Raised when a stored checkpoint cannot be understood."""


@dataclass(frozen=True)
class Checkpoint:
    """The point in time a collector has already collected up to."""

    last_seen_ms: int

    @classmethod
    def from_datetime(cls, moment: datetime) -> Checkpoint:
        """Build a checkpoint from an aware datetime."""
        return cls(last_seen_ms=int(moment.timestamp() * 1000))

    @classmethod
    def parse(cls, stored: str | None) -> Checkpoint | None:
        """Read a checkpoint previously written by `serialize`; None when there is none."""
        if stored is None or stored == "":
            return None
        try:
            return cls(last_seen_ms=int(stored))
        except ValueError as error:
            raise InvalidCheckpointError(f"checkpoint {stored!r} is not a timestamp") from error

    def serialize(self) -> str:
        """Render the checkpoint for storage in collector_state."""
        return str(self.last_seen_ms)

    def covers(self, time_created_ms: int) -> bool:
        """Report whether a message at this time is fully covered by the checkpoint.

        Strictly older messages are covered. A message sharing the checkpoint's exact
        millisecond is *not* covered, because a message written in that millisecond may
        have been still generating at the previous scan and only now carry its usage.
        Records are keyed by a stable event id, so re-reading that one row is harmless.
        """
        return time_created_ms < self.last_seen_ms

    def to_datetime(self) -> datetime:
        """Return the checkpoint as an aware UTC datetime."""
        return datetime.fromtimestamp(self.last_seen_ms / 1000, tz=timezone.utc)
