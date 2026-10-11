"""Tests for the scheduler and the application's own collection lifecycle.

The promise under test is that starting the server is enough: history is imported
once, and the dashboard keeps up afterwards, without anyone pressing a button and
without the scan blocking the API.
"""

import asyncio
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collectors.base import BaseCollector, ScanOutcome
from config.settings import Settings
from database.connection import Base
from database.repository import count_usage_events
from database.state import load_progress
from main import create_app
from schemas.usage import DiscoveryResult, UsageRecord
from sync.coordinator import SyncCoordinator
from sync.result import SyncResult
from sync.scheduler import SyncScheduler

UTC = timezone.utc
FIRST_MS = 1_700_000_000_000


def make_record(platform: str, event_id: str) -> UsageRecord:
    """A record standing in for one stored model call on `platform`."""
    return UsageRecord(
        platform=platform,
        provider_id=platform,
        model_id="space-bunny-free",
        session_id="ses_1",
        message_id=event_id,
        source_event_id=f"ses_1:{event_id}",
        timestamp=datetime.fromtimestamp(FIRST_MS / 1000, tz=UTC),
        input_tokens=90,
        output_tokens=10,
        total_tokens=100,
        consumption_tokens=100,
        usage_status="reported",
    )


class CountingCollector(BaseCollector):
    """A collector that reports how many times it was scanned."""

    def __init__(self, platform: str) -> None:
        self._platform = platform
        self.scans = 0

    @property
    def platform(self) -> str:
        return self._platform

    def discover(self) -> DiscoveryResult:
        return DiscoveryResult(
            platform=self.platform,
            available=True,
            source_path=f"/fake/{self.platform}",
            storage_format="fake",
        )

    def collect_history(self) -> list[UsageRecord]:
        return [make_record(self.platform, "msg_1")]

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        self.scans += 1
        return self.collect_history()

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        self.scans += 1
        return ScanOutcome(records=self.collect_history())


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database factory for the scheduler to write into."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def test_a_scan_runs_once_at_startup(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    collector = CountingCollector("cline")
    settings = Settings(database_path=tmp_path / "s.db", log_level="WARNING")
    scheduler = SyncScheduler(SyncCoordinator([collector], settings), session_factory, 3600)

    asyncio.run(scheduler.run_once())

    assert collector.scans == 1


def test_the_scheduler_repeats_on_its_interval(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    collector = CountingCollector("cline")
    settings = Settings(database_path=tmp_path / "s.db", log_level="WARNING")
    scheduler = SyncScheduler(SyncCoordinator([collector], settings), session_factory, 0.01)

    async def run_briefly() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(scheduler.run_periodically(stop))
        # Wait for the second scan rather than assuming a fixed sleep is long enough:
        # under a loaded machine this test ran in a suite, and 50 ms was not always
        # enough for a 10 ms interval to come round again.
        deadline = time.monotonic() + 5.0
        while collector.scans < 2 and time.monotonic() < deadline:
            await asyncio.sleep(0.005)
        stop.set()
        await task

    asyncio.run(run_briefly())

    assert collector.scans > 1


def test_stopping_the_scheduler_does_not_start_another_pass(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    # A long interval must not delay shutdown: closing the server should not wait
    # out the remaining time.
    collector = CountingCollector("cline")
    settings = Settings(database_path=tmp_path / "s.db", log_level="WARNING")
    scheduler = SyncScheduler(SyncCoordinator([collector], settings), session_factory, 3600)

    async def run_and_stop() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(scheduler.run_periodically(stop))
        await asyncio.sleep(0)
        stop.set()
        await asyncio.wait_for(task, timeout=1.0)

    asyncio.run(run_and_stop())

    assert collector.scans == 1


def test_a_failing_pass_does_not_kill_the_loop(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    class ExplodingCoordinator(SyncCoordinator):
        def run_all(
            self,
            session_factory: Callable[[], Session],
            *,
            from_scratch: bool = False,
        ) -> list[SyncResult]:
            raise RuntimeError("the database vanished")

    settings = Settings(database_path=tmp_path / "s.db", log_level="WARNING")
    scheduler = SyncScheduler(ExplodingCoordinator([], settings), session_factory, 0.01)

    async def run_briefly() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(scheduler.run_periodically(stop))
        await asyncio.sleep(0.05)
        stop.set()
        await task

    asyncio.run(run_briefly())  # must not raise


def test_starting_the_server_collects_without_being_asked(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "server.db",
        log_level="WARNING",
        sync_enabled=True,
        sync_interval_seconds=3600,
    )
    collector = CountingCollector("cline")
    application = create_app(settings)
    application.state.collectors = [collector]

    with TestClient(application) as client:
        # The first pass runs in the background, so wait for it rather than racing it.
        for _ in range(200):
            if collector.scans:
                break
            time.sleep(0.01)
        assert collector.scans >= 1
        response = client.get("/api/collector/status/cline")

    assert response.status_code == 200
    assert response.json()["platform"] == "cline"


def test_collecting_on_startup_stores_the_history_it_found(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "server.db",
        log_level="WARNING",
        sync_enabled=True,
        sync_interval_seconds=3600,
    )
    application = create_app(settings)
    cline = CountingCollector("cline")
    opencode = CountingCollector("opencode")
    application.state.collectors = [cline, opencode]

    with TestClient(application):
        # Platforms are scanned one after another, so wait for the last one rather
        # than for whichever happens to finish first.
        for _ in range(200):
            if opencode.scans:
                break
            time.sleep(0.01)

        with application.state.session_factory() as session:
            assert count_usage_events(session, "cline") == 1
            assert count_usage_events(session, "opencode") == 1
            assert load_progress(session, "cline") is not None


def test_collection_can_be_turned_off(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "server.db",
        log_level="WARNING",
        sync_enabled=False,
    )
    collector = CountingCollector("cline")
    application = create_app(settings)
    application.state.collectors = [collector]

    with TestClient(application) as client:
        response = client.get("/api/collector/status/cline")

    assert collector.scans == 0
    assert response.json()["last_scan_at"] is None


def test_manual_rescan_still_works_while_automatic_collection_is_on(tmp_path: Path) -> None:
    # Turning the scheduler on must not take the recovery path away.
    settings = Settings(
        database_path=tmp_path / "server.db",
        log_level="WARNING",
        sync_enabled=True,
        sync_interval_seconds=3600,
    )
    collector = CountingCollector("cline")
    application = create_app(settings)
    application.state.collectors = [collector]

    with TestClient(application) as client:
        response = client.post("/api/collector/rescan/cline")

    assert response.status_code == 200
    assert response.json()["platform"] == "cline"
    assert collector.scans >= 1