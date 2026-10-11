"""Phase 10 — the cross-cutting guarantees the per-platform suites imply, not state.

Every item on the Phase 10 checklist is exercised somewhere; the map below says
where. These tests cover the two that are easiest to leave implied because they
only mean anything once all four platforms exist together:

* **Application restarts do not duplicate records.** A restart is a brand-new
  coordinator over the *same* database, resuming from the saved checkpoints. It
  must be a no-op on every platform. (`test_rescanning_never_duplicates_any_platform`
  proved the manual `from_scratch` rescan is safe; this proves an ordinary restart
  is too.)

* **A restart after a source vanishes preserves history.** With one platform's
  store deleted, a restart skips that platform and leaves its imported rows and
  checkpoint in place, while the other three keep syncing.

Checklist coverage map (item -> home):
  Claude Code: discovery -> `test_locator.py`; JSONL parsing, input/output/cache
    extraction, missing usage, dedup, model switching, subagent (sidechain) usage,
    historical import -> `test_extractor.py`, `test_collector.py`,
    `test_claude_pipeline.py`; provider switching -> `test_providers.py`;
    interrupted sessions -> `test_user_lines_and_cost_state_are_never_collected`.
  Codex CLI: default/custom discovery -> `test_locator.py`; token-event parsing,
    cumulative-counter handling, per-turn usage, model-context attribution,
    provider identification, model switching, dedup -> `test_extractor.py`,
    `test_collector.py`, `test_providers.py`, `test_codex_pipeline.py`; session
    compaction & retry -> `test_per_call_usage_reconciles_to_the_session_rollup`
    (rollups stay monotonic) and `test_distinct_calls_stay_separate` (a retry is a
    new id, counted once); archived sessions read like active ones (file-based,
    archival is a DB flag) -> `test_locator.py` + `test_collector.py`.
  Shared regression: OpenCode/Cline functional -> their own suites; existing data
    preserved, shared DB, shared dedup, shared normalization, combined totals,
    platform/model/provider filters -> `test_all_platforms_sync.py`,
    `test_analytics_platforms.py`, `test_phase8_checklist.py`; restarts -> below.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collectors.registry import build_collectors
from config.settings import Settings
from database.connection import Base
from database.repository import count_usage_events
from database.state import load_progress
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
    return {"opencode": opencode, "cline": cline, "claude": claude, "codex": codex}


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


def test_an_application_restart_does_not_duplicate_any_platform(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    build_sync_coordinator(build_collectors(settings), settings).run_all(session_factory)

    # A restart: a fresh coordinator and fresh collectors over the same database,
    # resuming incrementally from the saved checkpoints (no from_scratch).
    restarted = build_sync_coordinator(build_collectors(settings), settings)
    second = restarted.run_all(session_factory)

    assert all(result.inserted == 0 for result in second)
    with session_factory() as session:
        for platform in PLATFORMS:
            assert count_usage_events(session, platform) == 1, platform


def test_a_restart_after_a_source_vanishes_preserves_history(
    settings: Settings,
    session_factory: sessionmaker[Session],
    four_stores: dict[str, object],
) -> None:
    build_sync_coordinator(build_collectors(settings), settings).run_all(session_factory)

    # Codex is uninstalled, then the app restarts. Its source is gone, so it is
    # skipped this pass, but everything already imported stays and the rest run on.
    shutil.rmtree(four_stores["codex"].codex_home)
    results = build_sync_coordinator(build_collectors(settings), settings).run_all(
        session_factory
    )

    by_platform = {result.platform: result for result in results}
    assert by_platform["codex"].failed is False
    assert by_platform["codex"].scanned == 0
    with session_factory() as session:
        assert count_usage_events(session, "codex") == 1  # history preserved
        assert load_progress(session, "codex") is not None
        for platform in ("opencode", "cline", "claude_code"):
            assert count_usage_events(session, platform) == 1, platform
