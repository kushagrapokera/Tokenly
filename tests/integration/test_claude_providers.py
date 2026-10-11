"""Phase 4 — provider attribution end to end, through the real pipeline.

Phase 4's checklist ("Test provider/model switching", "Handle missing
provider metadata", the correctness rules) exercised here at the level a
user sees: records synced from a fixture Claude Code store, aggregated the
way the dashboard does. Complements `tests/collectors/claude/test_providers.py`,
which states the rule table itself.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from aggregation.breakdown import breakdown_by_model
from aggregation.ranges import resolve_range
from collectors.claude import ClaudeCodeCollector
from config.settings import Settings
from database.connection import Base
from database.repository import sum_tokens
from sync.service import SyncService
from tests.collectors.claude.conftest import ClaudeStoreBuilder


@pytest.fixture
def claude_store(tmp_path: Path) -> Iterator[ClaudeStoreBuilder]:
    yield ClaudeStoreBuilder(projects_dir=tmp_path / "projects")


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def sync(store: ClaudeStoreBuilder, tmp_path: Path, factory: sessionmaker[Session]) -> None:
    settings = Settings(
        database_path=tmp_path / "tokenly.db",
        claude_data_dir=store.projects_dir.parent,
        log_level="WARNING",
    )
    with factory() as session:
        SyncService(ClaudeCodeCollector(settings)).run(session)


def test_provider_switching_within_one_session_splits_the_breakdown(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    # One session, three model requests through three different gateways;
    # per-request attribution keeps each provider's usage separate.
    claude_store.add_assistant_request(
        message_id="m-switc001", provider_prefix="openrouter/", line_count=1
    )
    claude_store.add_assistant_request(
        message_id="m-switc002", model="anthropic.claude-opus-4-6-v1:0", line_count=1
    )
    claude_store.add_assistant_request(message_id="m-switc003", line_count=1)  # bare, unknown

    sync(claude_store, tmp_path, session_factory)

    with session_factory() as session:
        rows = breakdown_by_model(session, resolve_range("all_time", "UTC"))

    by_provider = {row.provider_id: row.total_tokens for row in rows}
    assert by_provider == {"openrouter": 120, "bedrock": 120, "unknown": 120}


def test_the_same_model_through_two_gateways_stays_distinct(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    # `sonnet-4-5` typed once with an OpenRouter prefix and once bare: the
    # model id strings differ, and the plan requires no cross-provider merge.
    claude_store.add_assistant_request(
        message_id="m-gwrdc001", provider_prefix="openrouter/", model="sonnet-4-5", line_count=1
    )
    claude_store.add_assistant_request(message_id="m-gwrdc002", model="sonnet-4-5", line_count=1)

    sync(claude_store, tmp_path, session_factory)

    with session_factory() as session:
        rows = breakdown_by_model(session, resolve_range("all_time", "UTC"))

    identities = {(row.provider_id, row.model_id) for row in rows}
    assert identities == {("openrouter", "openrouter/sonnet-4-5"), ("unknown", "sonnet-4-5")}
    assert len(rows) == 2


def test_missing_model_metadata_is_counted_under_the_unknown_model(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    # An assistant line Claude Code wrote without a `message.model`.
    import json

    modelless_line = json.dumps(
        {
            "type": "assistant",
            "message": {"id": "m-nomodel1", "role": "assistant"},
            "timestamp": "2026-09-22T11:52:31.580Z",
            "sessionId": "927dbe1f-44e6-4165-badf-1f97622e5829",
        }
    )
    transcript = claude_store.add_session()
    transcript.write_text(modelless_line + "\n", encoding="utf-8")

    sync(claude_store, tmp_path, session_factory)

    with session_factory() as session:
        rows = breakdown_by_model(session, resolve_range("all_time", "UTC"))

    assert len(rows) == 1
    assert rows[0].model_id == "unknown"
    assert rows[0].provider_id == "unknown"
    assert rows[0].request_count == 1


def test_provider_totals_reconcile_with_the_platform_summary(
    claude_store: ClaudeStoreBuilder,
    tmp_path: Path,
    session_factory: sessionmaker[Session],
) -> None:
    claude_store.add_assistant_request(provider_prefix="openrouter/", line_count=1)
    claude_store.add_assistant_request(message_id="m-recon02", line_count=1)

    sync(claude_store, tmp_path, session_factory)

    from database.repository import count_usage_events

    with session_factory() as session:
        total = sum_tokens(session, "total_tokens", platform="claude_code")

    assert count_usage_events(session, "claude_code") == 2
    assert total == 240
