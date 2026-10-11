"""Codex through the real shared pipeline: one database, one sync service.

The Phase 1 compatibility tests proved synthetic `codex` records flow through the
pipeline; these drive the *actual collector* — reading a fixture-built Codex home
through `CodexCollector`, `SyncService`, `upsert_usage_records`, and the shared
aggregations — and assert what a user would see. The traps they exist to catch
are the `event_msg`/`token_count` echo and the turn/thread rollups both being
ingested alongside the per-call usage, plus checkpoint resumptions across restarts.
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
from collectors.claude import ClaudeCodeCollector
from collectors.codex import CodexCollector
from config.settings import Settings
from database.connection import Base
from database.repository import count_usage_events
from database.state import load_progress
from sync.result import SyncResult
from sync.service import SyncService
from tests.collectors.claude.conftest import ClaudeStoreBuilder
from tests.collectors.codex.conftest import CodexStoreBuilder


@pytest.fixture
def codex_store(tmp_path: Path) -> Iterator[CodexStoreBuilder]:
    """A stand-in Codex home in this test's temp directory."""
    yield CodexStoreBuilder(codex_home=tmp_path / "codex")


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database factory."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def settings_for(tmp_path: Path, store: CodexStoreBuilder) -> Settings:
    return Settings(
        database_path=tmp_path / "tokenly.db",
        codex_home=store.codex_home,
        log_level="WARNING",
        rescan_overlap_ms=0,
    )


def sync(
    codex_store: CodexStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> SyncResult:
    """Run one sync pass through the real service."""
    with session_factory() as session:
        return SyncService(CodexCollector(settings_for(tmp_path, codex_store))).run(session)


# --- historical import ---


def test_the_first_sync_imports_one_record_per_usage_call(
    codex_store: CodexStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    codex_store.add_usage_call(input_tokens=100, output_tokens=20)
    codex_store.add_token_count_event(input_tokens=100, output_tokens=20)  # the echo
    codex_store.add_usage_call(input_tokens=50, output_tokens=10)

    result = sync(codex_store, tmp_path, session_factory)

    assert result.failed is False
    assert result.mode == "historical"
    assert result.inserted == 2
    with session_factory() as session:
        assert count_usage_events(session, "codex") == 2


def test_totals_are_the_per_call_sums_not_the_rollups_or_echoes(
    codex_store: CodexStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    # Two calls in one turn: 120 + 60 = 180. The turn rollup (180) and the
    # token_count echo (120) both sit in the same file and must not be added.
    codex_store.add_usage_call(input_tokens=100, output_tokens=20)
    codex_store.add_usage_call(input_tokens=50, output_tokens=10)
    codex_store.add_token_count_event(input_tokens=100, output_tokens=20)

    sync(codex_store, tmp_path, session_factory)

    with session_factory() as session:
        summary = summarize_range(session, resolve_range("all_time", "UTC"))

    assert summary.request_count == 2
    assert summary.total_tokens == 180


def test_repeated_syncs_do_not_double_count(
    codex_store: CodexStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    codex_store.add_usage_call(input_tokens=100, output_tokens=20)
    codex_store.add_usage_call(input_tokens=7, output_tokens=3)

    for _ in range(3):
        sync(codex_store, tmp_path, session_factory)
    with session_factory() as session:
        SyncService(CodexCollector(settings_for(tmp_path, codex_store))).run(
            session, from_scratch=True
        )

    with session_factory() as session:
        summary = summarize_range(session, resolve_range("all_time", "UTC"))

    assert summary.request_count == 2
    assert summary.total_tokens == 130  # 120 + 10, not a repeated multiple


def test_the_checkpoint_advances(
    codex_store: CodexStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    codex_store.add_usage_call(timestamp="2026-09-22T11:00:00.000Z", response_id="resp-ckpoint1")
    sync(codex_store, tmp_path, session_factory)

    with session_factory() as session:
        progress = load_progress(session, "codex")

    assert progress is not None
    assert progress.checkpoint is not None
    from datetime import datetime, timezone

    expected_ms = int(datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert int(progress.checkpoint) == expected_ms  # 2026-09-22T11:00Z


# --- provider/model breakdown ---


def test_breakdown_groups_by_the_joined_model_and_provider(
    codex_store: CodexStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    codex_store.add_usage_call()  # deepseek / deepseek-flash via the join

    sync(codex_store, tmp_path, session_factory)

    with session_factory() as session:
        rows = breakdown_by_model(session, resolve_range("all_time", "UTC"))

    assert {(row.provider_id, row.model_id) for row in rows} == {
        ("deepseek", "deepseek-flash")
    }


# --- coexistence with existing platforms ---


def test_codex_and_claude_share_one_database_without_colliding(
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    codex_store = CodexStoreBuilder(codex_home=tmp_path / "codex")
    codex_store.add_usage_call()
    claude_store = ClaudeStoreBuilder(projects_dir=tmp_path / "projects")
    claude_store.add_assistant_request(line_count=2)
    settings = Settings(
        database_path=tmp_path / "tokenly.db",
        codex_home=codex_store.codex_home,
        claude_data_dir=claude_store.projects_dir.parent,
        log_level="WARNING",
    )

    with session_factory() as session:
        SyncService(CodexCollector(settings)).run(session)
    with session_factory() as session:
        SyncService(ClaudeCodeCollector(settings)).run(session)

    with session_factory() as session:
        assert count_usage_events(session, "codex") == 1
        assert count_usage_events(session, "claude_code") == 1
        codex_only = summarize_range(
            session, resolve_range("all_time", "UTC"), UsageFilter(platform="codex")
        )

    assert codex_only.request_count == 1
    assert codex_only.total_tokens == 120
