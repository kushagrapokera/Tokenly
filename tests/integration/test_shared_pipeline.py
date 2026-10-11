"""Shared OpenCode + Cline integration tests: one database, one pipeline.

These tests prove the Phase 2 promise — Cline flows through the same
normalization, persistence, sync, and aggregation as OpenCode, platform
filtering separates them, combined totals add up, and OpenCode history is
untouched by Cline syncs.
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
from collectors.cline import ClineCollector
from collectors.opencode import OpenCodeCollector
from config.settings import Settings
from database.connection import Base
from database.repository import count_usage_events
from sync.service import SyncService
from tests.collectors.cline.conftest import ClineStoreBuilder
from tests.collectors.opencode.conftest import OpenCodeDatabaseBuilder


@pytest.fixture
def opencode_db(tmp_path: Path) -> Iterator[OpenCodeDatabaseBuilder]:
    """A stand-in OpenCode database in this test's temp directory."""
    yield OpenCodeDatabaseBuilder(path=tmp_path / "opencode.db")


@pytest.fixture
def cline_store(tmp_path: Path) -> Iterator[ClineStoreBuilder]:
    """A stand-in Cline data directory in this test's temp directory."""
    yield ClineStoreBuilder(data_dir=tmp_path / "cline-data")


def make_app_db(tmp_path: Path) -> tuple[sessionmaker[Session], Path]:
    """Create a fresh Tokenly database and return its session factory."""
    db_path = tmp_path / "shared.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), db_path


def sync_all(session_factory: sessionmaker[Session], settings: Settings) -> None:
    """Run both collectors once through the real sync service."""
    with session_factory() as session:
        SyncService(OpenCodeCollector(settings)).run(session)
    with session_factory() as session:
        SyncService(ClineCollector(settings)).run(session)


def test_both_collectors_share_one_database(
    tmp_path: Path,
    opencode_db: OpenCodeDatabaseBuilder,
    cline_store: ClineStoreBuilder,
) -> None:
    opencode_db.add_assistant_message()
    cline_store.add_assistant_message()
    factory, _ = make_app_db(tmp_path)
    settings = Settings(
        database_path=tmp_path / "shared.db",
        opencode_data_dir=opencode_db.path.parent,
        cline_data_dir=cline_store.data_dir,
    )

    sync_all(factory, settings)

    with factory() as session:
        assert count_usage_events(session) == 2
        assert count_usage_events(session, "opencode") == 1
        assert count_usage_events(session, "cline") == 1


def test_platform_filtering_separates_the_two_sources(
    tmp_path: Path,
    opencode_db: OpenCodeDatabaseBuilder,
    cline_store: ClineStoreBuilder,
) -> None:
    opencode_db.add_assistant_message()
    cline_store.add_assistant_message()
    factory, _ = make_app_db(tmp_path)
    settings = Settings(
        database_path=tmp_path / "shared.db",
        opencode_data_dir=opencode_db.path.parent,
        cline_data_dir=cline_store.data_dir,
    )
    sync_all(factory, settings)

    window = resolve_range("all_time", "UTC")
    with factory() as session:
        everything = summarize_range(session, window)
        opencode_only = summarize_range(session, window, UsageFilter(platform="opencode"))
        cline_only = summarize_range(session, window, UsageFilter(platform="cline"))

    assert everything.request_count == 2
    assert opencode_only.request_count == 1
    assert cline_only.request_count == 1
    assert everything.total_tokens == opencode_only.total_tokens + cline_only.total_tokens


def test_combined_model_breakdown_keeps_platforms_distinct(
    tmp_path: Path,
    opencode_db: OpenCodeDatabaseBuilder,
    cline_store: ClineStoreBuilder,
) -> None:
    opencode_db.add_assistant_message(message_overrides={"modelID": "shared-model"})
    cline_store.add_assistant_message(
        message_overrides={"modelInfo": {"id": "shared-model", "provider": "cline"}}
    )
    factory, _ = make_app_db(tmp_path)
    settings = Settings(
        database_path=tmp_path / "shared.db",
        opencode_data_dir=opencode_db.path.parent,
        cline_data_dir=cline_store.data_dir,
    )
    sync_all(factory, settings)

    window = resolve_range("all_time", "UTC")
    with factory() as session:
        models = breakdown_by_model(session, window)

    # Same model name on two platforms must not merge.
    assert len(models) == 2


def test_cline_sync_leaves_opencode_history_intact(
    tmp_path: Path,
    opencode_db: OpenCodeDatabaseBuilder,
    cline_store: ClineStoreBuilder,
) -> None:
    opencode_db.add_assistant_message()
    factory, _ = make_app_db(tmp_path)
    settings = Settings(
        database_path=tmp_path / "shared.db",
        opencode_data_dir=opencode_db.path.parent,
        cline_data_dir=cline_store.data_dir,
    )
    with factory() as session:
        SyncService(OpenCodeCollector(settings)).run(session)
    with factory() as session:
        before = count_usage_events(session, "opencode")

    cline_store.add_assistant_message()
    with factory() as session:
        SyncService(ClineCollector(settings)).run(session)

    with factory() as session:
        assert count_usage_events(session, "opencode") == before
        assert count_usage_events(session, "cline") == 1


def test_cline_and_opencode_ids_cannot_collide(
    tmp_path: Path,
    opencode_db: OpenCodeDatabaseBuilder,
    cline_store: ClineStoreBuilder,
) -> None:
    """Both platforms use `msg_*` ids — the platform column must keep them apart."""
    opencode_db.add_assistant_message(message_id="msg_0001")
    cline_store.add_assistant_message(message_id="msg_0001")
    factory, _ = make_app_db(tmp_path)
    settings = Settings(
        database_path=tmp_path / "shared.db",
        opencode_data_dir=opencode_db.path.parent,
        cline_data_dir=cline_store.data_dir,
    )

    sync_all(factory, settings)

    with factory() as session:
        assert count_usage_events(session) == 2
