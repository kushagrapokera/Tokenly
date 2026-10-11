"""Claude Code through the real shared pipeline: one database, one sync service.

The Phase 1 compatibility tests proved synthetic `claude_code` records flow
through the pipeline; these drive the *actual collector* — reading
a fixture-built Claude Code store through `ClaudeCodeCollector`, `SyncService`,
`upsert_usage_records`, and the shared aggregations — and assert what a user
would see. The trap they exist to catch is the repeated-line triple counting
plus the checkpoint resumptions that make it dangerous across restarts.
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
from collectors.opencode import OpenCodeCollector
from config.settings import Settings
from database.connection import Base
from database.repository import count_usage_events
from database.state import load_progress
from sync.result import SyncResult
from sync.service import SyncService
from tests.collectors.claude.conftest import ClaudeStoreBuilder
from tests.collectors.opencode.conftest import OpenCodeDatabaseBuilder


@pytest.fixture
def claude_store(tmp_path: Path) -> Iterator[ClaudeStoreBuilder]:
    """A stand-in Claude Code store in this test's temp directory."""
    yield ClaudeStoreBuilder(projects_dir=tmp_path / "projects")


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database factory."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def settings_for(tmp_path: Path, store: ClaudeStoreBuilder) -> Settings:
    return Settings(
        database_path=tmp_path / "tokenly.db",
        claude_data_dir=store.projects_dir.parent,
        log_level="WARNING",
        rescan_overlap_ms=0,
    )


def sync(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> SyncResult:
    """Run one sync pass through the real service."""
    with session_factory() as session:
        return SyncService(ClaudeCodeCollector(settings_for(tmp_path, claude_store))).run(session)


# --- historical import ---


def test_the_first_sync_imports_one_record_per_request(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    claude_store.add_assistant_request(line_count=4)  # 4 lines, 1 real request
    claude_store.add_assistant_request(input_tokens=50, output_tokens=10, line_count=2)

    result = sync(claude_store, tmp_path, session_factory)

    assert result.failed is False
    assert result.mode == "historical"
    assert result.inserted == 2
    with session_factory() as session:
        assert count_usage_events(session, "claude_code") == 2


def test_collapsed_totals_are_the_request_totals_not_the_line_totals(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    claude_store.add_assistant_request(line_count=5)  # 100 in + 20 out, written 5 times

    sync(claude_store, tmp_path, session_factory)

    with session_factory() as session:
        summary = summarize_range(session, resolve_range("all_time", "UTC"))

    assert summary.request_count == 1
    assert summary.total_tokens == 120  # 5x120 would be the triple-count failure


# --- incremental sync and restarts ---


def test_a_second_sync_after_new_usage_inserts_only_the_new_request(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    claude_store.add_assistant_request(
        timestamp="2026-09-22T11:00:00.000Z", message_id="m-early0002", line_count=2
    )
    sync(claude_store, tmp_path, session_factory)

    claude_store.add_assistant_request(
        timestamp="2026-09-22T12:00:00.000Z", message_id="m-later0003", line_count=3
    )
    result = sync(claude_store, tmp_path, session_factory)

    assert result.mode == "incremental"
    assert result.inserted == 1
    with session_factory() as session:
        assert count_usage_events(session, "claude_code") == 2


def test_repeated_syncs_and_full_rescans_never_inflate_totals(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    claude_store.add_assistant_request(line_count=3)
    claude_store.add_assistant_request(input_tokens=7, output_tokens=3, line_count=1)

    for _ in range(3):
        sync(claude_store, tmp_path, session_factory)
    with session_factory() as session:
        SyncService(
            ClaudeCodeCollector(settings_for(tmp_path, claude_store))
        ).run(session, from_scratch=True)

    with session_factory() as session:
        summary = summarize_range(session, resolve_range("all_time", "UTC"))

    assert summary.request_count == 2
    assert summary.total_tokens == 130  # 120 + 10, not a repeated-line multiple


def test_the_checkpoint_advances_and_resumes(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    claude_store.add_assistant_request(
        timestamp="2026-09-22T11:00:00.000Z", message_id="m-ckpoint1", line_count=2
    )
    sync(claude_store, tmp_path, session_factory)

    with session_factory() as session:
        progress = load_progress(session, "claude_code")

    assert progress is not None
    assert progress.checkpoint is not None
    from datetime import datetime, timezone

    expected_ms = int(datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert int(progress.checkpoint) == expected_ms  # 2026-09-22T11:00Z


# --- provider/model breakdown ---


def test_breakdown_groups_by_model_with_prefix_based_providers(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    claude_store.add_assistant_request(provider_prefix="openrouter/", line_count=1)
    claude_store.add_assistant_request(message_id="m-anth001", line_count=1)

    sync(claude_store, tmp_path, session_factory)

    with session_factory() as session:
        rows = breakdown_by_model(session, resolve_range("all_time", "UTC"))

    identities = {(row.provider_id, row.model_id) for row in rows}
    assert identities == {
        ("openrouter", "openrouter/claude-sonnet-4-5"),
        ("unknown", "claude-sonnet-4-5"),
    }


# --- coexistence with existing platforms ---


def test_claude_and_opencode_share_one_database_without_colliding(
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    opencode_db = OpenCodeDatabaseBuilder(path=tmp_path / "opencode.db")
    opencode_db.add_assistant_message()
    claude_store = ClaudeStoreBuilder(projects_dir=tmp_path / "projects")
    claude_store.add_assistant_request(line_count=2)
    settings = Settings(
        database_path=tmp_path / "tokenly.db",
        opencode_data_dir=opencode_db.path.parent,
        claude_data_dir=claude_store.projects_dir.parent,
        log_level="WARNING",
    )

    with session_factory() as session:
        SyncService(OpenCodeCollector(settings)).run(session)
    with session_factory() as session:
        SyncService(ClaudeCodeCollector(settings)).run(session)

    with session_factory() as session:
        assert count_usage_events(session, "opencode") == 1
        assert count_usage_events(session, "claude_code") == 1
        summary = summarize_range(session, resolve_range("all_time", "UTC"))
        claude_only = summarize_range(
            session, resolve_range("all_time", "UTC"), UsageFilter(platform="claude_code")
        )

    assert summary.total_tokens == claude_only.total_tokens + 120
    assert claude_only.request_count == 1
