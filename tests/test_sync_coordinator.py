"""Tests for the coordinator: every platform is scanned, and none can stop another.

`SyncService` already guarantees that one collector's own failures are recorded
rather than raised. These tests cover the layer above it, which decides which
platforms are scanned at all and what one platform's failure does to the others.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collectors.base import BaseCollector, ScanOutcome
from config.settings import Settings
from database.connection import Base
from database.repository import count_usage_events
from database.state import load_progress
from schemas.usage import DiscoveryResult, UsageRecord
from sync.coordinator import SyncCoordinator

UTC = timezone.utc
FIRST_MS = 1_700_000_000_000


def make_record(platform: str, event_id: str, timestamp_ms: int = FIRST_MS) -> UsageRecord:
    """A record standing in for one stored model call on `platform`."""
    return UsageRecord(
        platform=platform,
        provider_id=platform,
        model_id="space-bunny-free",
        session_id="ses_1",
        message_id=event_id,
        source_event_id=f"ses_1:{event_id}",
        timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC),
        input_tokens=90,
        output_tokens=10,
        total_tokens=100,
        consumption_tokens=100,
        usage_status="reported",
    )


class StubCollector(BaseCollector):
    """A collector whose availability, records, and failures a test controls."""

    def __init__(
        self,
        platform: str,
        records: list[UsageRecord] | None = None,
        *,
        available: bool = True,
        raises: Exception | None = None,
        discovery_raises: Exception | None = None,
    ) -> None:
        self._platform = platform
        self._records = records or []
        self._available = available
        self._raises = raises
        self._discovery_raises = discovery_raises
        self.scans: list[str | None] = []

    @property
    def platform(self) -> str:
        return self._platform

    def discover(self) -> DiscoveryResult:
        if self._discovery_raises is not None:
            raise self._discovery_raises
        return DiscoveryResult(
            platform=self.platform,
            available=self._available,
            source_path=f"/fake/{self.platform}",
            storage_format="fake",
        )

    def collect_history(self) -> list[UsageRecord]:
        return list(self._records)

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        self.scans.append(checkpoint)
        if self._raises is not None:
            raise self._raises
        return list(self._records)

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        self.scans.append(checkpoint)
        if self._raises is not None:
            raise self._raises
        return ScanOutcome(records=list(self._records))


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database factory for the coordinator to write into."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings with no rescan overlap, so resume points stay predictable."""
    return Settings(
        database_path=tmp_path / "settings.db",
        log_level="WARNING",
        rescan_overlap_ms=0,
    )


def test_every_registered_collector_is_scanned(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    coordinator = SyncCoordinator(
        [
            StubCollector("opencode", [make_record("opencode", "msg_1")]),
            StubCollector("cline", [make_record("cline", "msg_1")]),
        ],
        settings,
    )

    results = coordinator.run_all(session_factory)

    assert [result.platform for result in results] == ["opencode", "cline"]
    assert all(result.succeeded for result in results)
    with session_factory() as session:
        assert count_usage_events(session, "opencode") == 1
        assert count_usage_events(session, "cline") == 1


def test_a_failing_collector_does_not_stop_the_others(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    coordinator = SyncCoordinator(
        [
            StubCollector("opencode", [make_record("opencode", "msg_1")]),
            StubCollector("cline", raises=RuntimeError("store is unreadable")),
            StubCollector("codex", [make_record("codex", "msg_1")]),
        ],
        settings,
    )

    results = coordinator.run_all(session_factory)

    by_platform = {result.platform: result for result in results}
    assert by_platform["cline"].failed is True
    assert "store is unreadable" in by_platform["cline"].error_message
    assert by_platform["opencode"].succeeded is True
    assert by_platform["codex"].succeeded is True
    with session_factory() as session:
        assert count_usage_events(session, "opencode") == 1
        assert count_usage_events(session, "codex") == 1


def test_an_absent_platform_is_skipped_rather_than_marked_failed(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    # Not having Cline installed is a normal state, not an error to record.
    absent = StubCollector("cline", [make_record("cline", "msg_1")], available=False)
    coordinator = SyncCoordinator(
        [absent, StubCollector("opencode", [make_record("opencode", "msg_1")])],
        settings,
    )

    results = coordinator.run_all(session_factory)

    by_platform = {result.platform: result for result in results}
    assert by_platform["cline"].failed is False
    assert by_platform["cline"].scanned == 0
    assert absent.scans == []
    with session_factory() as session:
        assert load_progress(session, "cline") is None
        assert count_usage_events(session, "cline") == 0


def test_discovery_that_raises_is_treated_as_unavailable(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    coordinator = SyncCoordinator(
        [StubCollector("cline", discovery_raises=OSError("permission denied"))],
        settings,
    )

    results = coordinator.run_all(session_factory)

    assert results[0].failed is False
    assert results[0].scanned == 0


def test_repeated_passes_never_inflate_a_total(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    # What a restart looks like from the coordinator's side: the same history is
    # scanned again and must land as updates, not as new usage.
    coordinator = SyncCoordinator(
        [
            StubCollector("cline", [make_record("cline", "msg_1")]),
            StubCollector("opencode", [make_record("opencode", "msg_1")]),
        ],
        settings,
    )

    coordinator.run_all(session_factory)
    second = coordinator.run_all(session_factory)

    assert all(result.inserted == 0 for result in second)
    with session_factory() as session:
        assert count_usage_events(session, "cline") == 1
        assert count_usage_events(session, "opencode") == 1


def test_each_platform_resumes_from_its_own_checkpoint(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    cline = StubCollector("cline", [make_record("cline", "msg_1")])
    opencode = StubCollector("opencode", [make_record("opencode", "msg_1")])
    coordinator = SyncCoordinator([cline, opencode], settings)

    coordinator.run_all(session_factory)
    coordinator.run_all(session_factory)

    assert cline.scans[-1] is not None
    assert opencode.scans[-1] is not None
    assert cline.scans[-1] == opencode.scans[-1] == str(FIRST_MS)


def test_a_from_scratch_pass_ignores_stored_checkpoints(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    collector = StubCollector("cline", [make_record("cline", "msg_1")])
    coordinator = SyncCoordinator([collector], settings)
    coordinator.run_all(session_factory)

    coordinator.run_all(session_factory, from_scratch=True)

    assert collector.scans[-1] is None
    with session_factory() as session:
        assert count_usage_events(session, "cline") == 1


def test_the_coordinator_reports_the_platforms_it_manages(settings: Settings) -> None:
    coordinator = SyncCoordinator(
        [StubCollector("opencode"), StubCollector("cline")],
        settings,
    )

    assert coordinator.platforms == ["opencode", "cline"]