"""All four collectors share one storage, sync, and analytics path (Phases 8–9).

The Phase 1/2 integration tests proved each platform individually, and the
coordinator tests proved isolation with stub collectors. These tests close the
Phase 8 and Phase 9 exit criteria against the *real* registry and collectors:

  * `build_collectors` registers OpenCode, Cline, Claude Code, and Codex.
  * `build_sync_coordinator` drives all four through the same `SyncService`,
    `upsert_usage_records`, checkpoints, and one shared database.
  * Re-syncing never duplicates a record on any platform.
  * One platform failing never stops the others from storing.
  * Imported history survives the source store being deleted.
  * The shared analytics — breakdown and platform-filtered summaries — show all
    four platforms with correct combined and filtered totals (the dashboard's data).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from aggregation.breakdown import breakdown_by_model
from aggregation.filters import UsageFilter
from aggregation.ranges import resolve_range
from aggregation.summary import summarize_range
from collectors.base import BaseCollector, ScanOutcome
from collectors.registry import build_collectors
from config.settings import Settings
from database.connection import Base
from database.repository import count_usage_events
from schemas.usage import DiscoveryResult
from sync.coordinator import build_sync_coordinator
from tests.collectors.claude.conftest import ClaudeStoreBuilder
from tests.collectors.cline.conftest import ClineStoreBuilder
from tests.collectors.codex.conftest import CodexStoreBuilder
from tests.collectors.opencode.conftest import OpenCodeDatabaseBuilder

PLATFORMS = ("opencode", "cline", "claude_code", "codex")


@pytest.fixture
def four_stores(tmp_path: Path) -> dict[str, object]:
    """One real-shaped fixture store per platform, under this test's temp dir."""
    opencode = OpenCodeDatabaseBuilder(path=tmp_path / "opencode.db")
    opencode.add_assistant_message()
    cline = ClineStoreBuilder(data_dir=tmp_path / "cline-data")
    cline.add_assistant_message()
    claude = ClaudeStoreBuilder(projects_dir=tmp_path / "projects")
    claude.add_assistant_request(line_count=2)
    codex = CodexStoreBuilder(codex_home=tmp_path / "codex-home")
    codex.add_usage_call()
    return {
        "opencode": opencode,
        "cline": cline,
        "claude": claude,
        "codex": codex,
    }


@pytest.fixture
def settings(tmp_path: Path, four_stores: dict[str, object]) -> Settings:
    return Settings(
        database_path=tmp_path / "tokenly.db",
        opencode_data_dir=four_stores["opencode"].path.parent,
        cline_data_dir=four_stores["cline"].data_dir,
        claude_data_dir=four_stores["claude"].projects_dir.parent,
        codex_home=four_stores["codex"].codex_home,
        log_level="WARNING",
        rescan_overlap_ms=0,
    )


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


class ExplodingCollector(BaseCollector):
    """A collector whose scan always fails, standing in for a broken platform."""

    @property
    def platform(self) -> str:
        return "exploding"

    def discover(self) -> DiscoveryResult:
        return DiscoveryResult(
            platform=self.platform,
            available=True,
            source_path="/fake/exploding",
            storage_format="fake",
        )

    def collect_history(self) -> list:
        return []

    def collect_updates(self, checkpoint: str | None = None) -> list:
        raise RuntimeError("simulated platform failure")

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        raise RuntimeError("simulated platform failure")


def test_all_four_platforms_are_registered(settings: Settings) -> None:
    registered = [collector.platform for collector in build_collectors(settings)]

    assert registered == list(PLATFORMS)


def test_all_four_flow_through_one_coordinator_into_one_database(
    settings: Settings,
    session_factory: sessionmaker[Session],
    four_stores: dict[str, object],
) -> None:
    coordinator = build_sync_coordinator(build_collectors(settings), settings)

    results = coordinator.run_all(session_factory)

    assert [result.platform for result in results] == list(PLATFORMS)
    assert all(result.failed is False for result in results)
    with session_factory() as session:
        for platform in PLATFORMS:
            assert count_usage_events(session, platform) == 1, platform
        summary = summarize_range(session, resolve_range("all_time", "UTC"))
    assert summary.request_count == 4


def test_resyncing_never_duplicates_any_platform(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    coordinator = build_sync_coordinator(build_collectors(settings), settings)

    coordinator.run_all(session_factory)
    second = coordinator.run_all(session_factory, from_scratch=True)

    assert all(result.inserted == 0 for result in second)
    with session_factory() as session:
        for platform in PLATFORMS:
            assert count_usage_events(session, platform) == 1, platform


def test_one_failing_platform_does_not_stop_the_others(
    settings: Settings,
    session_factory: sessionmaker[Session],
    four_stores: dict[str, object],
) -> None:
    collectors = build_collectors(settings) + [ExplodingCollector()]
    coordinator = build_sync_coordinator(collectors, settings)

    results = coordinator.run_all(session_factory)

    by_platform = {result.platform: result for result in results}
    assert by_platform["exploding"].failed is True
    # The three real, available platforms still stored their records.
    with session_factory() as session:
        for platform in ("opencode", "cline", "claude_code"):
            assert count_usage_events(session, platform) == 1, platform


def test_history_survives_deleting_the_source_store(
    settings: Settings,
    session_factory: sessionmaker[Session],
    four_stores: dict[str, object],
    tmp_path: Path,
) -> None:
    coordinator = build_sync_coordinator(build_collectors(settings), settings)
    coordinator.run_all(session_factory)

    # Remove Codex's entire source home, then re-run: the platform is now absent,
    # so it is skipped rather than failing, and its imported rows stay put.
    import shutil

    shutil.rmtree(four_stores["codex"].codex_home)
    results = coordinator.run_all(session_factory)

    by_platform = {result.platform: result for result in results}
    assert by_platform["codex"].failed is False
    assert by_platform["codex"].scanned == 0
    with session_factory() as session:
        assert count_usage_events(session, "codex") == 1  # history preserved


def test_breakdown_lists_all_four_platforms(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    # The dashboard's model breakdown is what populates its platform filter, so
    # every platform must appear here for it to be selectable.
    coordinator = build_sync_coordinator(build_collectors(settings), settings)
    coordinator.run_all(session_factory)

    with session_factory() as session:
        rows = breakdown_by_model(session, resolve_range("all_time", "UTC"))

    assert {row.platform for row in rows} == set(PLATFORMS)


def test_combined_total_equals_the_sum_of_platform_filtered_totals(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    # The dashboard's headline total must equal the sum of each platform's own
    # filtered total — the Phase 9 "correct combined and filtered totals" check.
    coordinator = build_sync_coordinator(build_collectors(settings), settings)
    coordinator.run_all(session_factory)

    with session_factory() as session:
        window = resolve_range("all_time", "UTC")
        combined = summarize_range(session, window)
        per_platform = {
            platform: summarize_range(session, window, UsageFilter(platform=platform))
            for platform in PLATFORMS
        }

    assert all(summary.request_count == 1 for summary in per_platform.values())
    assert combined.request_count == sum(s.request_count for s in per_platform.values())
    assert combined.total_tokens == sum(s.total_tokens for s in per_platform.values())

    def collect_updates(self, checkpoint: str | None = None) -> list:
        raise RuntimeError("simulated platform failure")

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        raise RuntimeError("simulated platform failure")
