"""Collector interface that every platform integration implements."""

from abc import ABC, abstractmethod

from schemas.usage import DiscoveryResult, UsageRecord


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
