"""Cline usage passing through the shared pipeline (implementation.md Phase 3).

Phase 3 asks for one thing above all: Cline records travel the same route as
OpenCode's — the same normalization, deduplication, persistence, and
aggregation — with no parallel implementation. These tests drive a stand-in
Cline store all the way from source file to aggregate and pin the cases the
phase calls out as risky: multiple models in one session, provider-specific
identifiers, records that arrive after a checkpoint, retries, subagent usage,
session totals versus request totals, and overlapping token categories.

`test_shared_pipeline.py` covers the cross-platform contract (one database,
platform filtering, no id collisions). This file covers what Cline specifically
brings to those same services.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from aggregation.filters import UsageFilter
from aggregation.ranges import resolve_range
from aggregation.summary import summarize_range
from collectors.cline import ClineCollector
from config.settings import Settings
from database.connection import Base
from database.models import UsageEvent
from database.repository import count_usage_events, query_usage_events
from sync.service import SyncService
from tests.collectors.cline.conftest import ClineStoreBuilder

FIRST_MS = 1_790_495_317_187
SECOND_MS = 1_790_495_900_000


@pytest.fixture
def cline_store(tmp_path: Path) -> Iterator[ClineStoreBuilder]:
    """A stand-in Cline data directory in this test's temp directory."""
    yield ClineStoreBuilder(data_dir=tmp_path / "cline-data")


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database, separate from the source store it reads."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)


def collector_for(cline_store: ClineStoreBuilder) -> ClineCollector:
    """A collector pointed at the stand-in store."""
    return ClineCollector(Settings(cline_data_dir=cline_store.data_dir))


def sync_once(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
    *,
    from_scratch: bool = False,
) -> None:
    """Run one synchronization pass through the real collector and service."""
    with session_factory() as session:
        SyncService(collector_for(cline_store)).run(session, from_scratch=from_scratch)


def stored_events(session_factory: sessionmaker[Session]) -> list[UsageEvent]:
    """Every stored Cline event, oldest first."""
    with session_factory() as session:
        return list(query_usage_events(session, platform="cline"))


def stored_raw_usage(session_factory: sessionmaker[Session]) -> dict[str, Any]:
    """The preserved raw usage of the one stored event, decoded from its JSON column."""
    with session_factory() as session:
        raw = query_usage_events(session, platform="cline")[0].raw_usage
    decoded = json.loads(raw)
    assert isinstance(decoded, dict)
    return cast(dict[str, Any], decoded)


def all_time_summary(session_factory: sessionmaker[Session]) -> float:
    """Total tokens Cline has stored across every range."""
    with session_factory() as session:
        window = resolve_range("all_time", "UTC")
        return summarize_range(session, window, UsageFilter(platform="cline")).total_tokens


def test_a_first_run_imports_the_whole_history_and_stores_it_once(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    cline_store.add_assistant_message(time_created_ms=FIRST_MS)
    cline_store.add_assistant_message(time_created_ms=SECOND_MS)

    sync_once(cline_store, session_factory)

    with session_factory() as session:
        assert count_usage_events(session, "cline") == 2
    assert all_time_summary(session_factory) == 240


def test_scanning_repeatedly_updates_rows_instead_of_adding_them(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    cline_store.add_assistant_message()

    sync_once(cline_store, session_factory)
    sync_once(cline_store, session_factory)
    sync_once(cline_store, session_factory)

    with session_factory() as session:
        assert count_usage_events(session, "cline") == 1
    assert all_time_summary(session_factory) == 120


def test_multiple_models_in_one_session_stay_separate(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    # One session that switched models: attribution comes from each message's own
    # modelInfo, never from the session envelope's model column.
    cline_store.add_assistant_message(
        {"modelInfo": {"id": "cline-free/gemini-3.8-flash", "provider": "cline"}},
        session_id="ses_mixed",
    )
    cline_store.add_assistant_message(
        {"modelInfo": {"id": "stealth/space-bunny-alpha", "provider": "cline"}},
        session_id="ses_mixed",
        time_created_ms=SECOND_MS,
    )

    sync_once(cline_store, session_factory)

    totals = {(event.model_id, event.total_tokens) for event in stored_events(session_factory)}
    assert totals == {
        ("cline-free/gemini-3.8-flash", 120),
        ("stealth/space-bunny-alpha", 120),
    }


def test_two_providers_serving_one_model_name_stay_distinct(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    cline_store.add_assistant_message(
        {"modelInfo": {"id": "shared-model", "provider": "cline"}},
        session_id="ses_a",
    )
    cline_store.add_assistant_message(
        {"modelInfo": {"id": "shared-model", "provider": "openrouter"}},
        session_id="ses_b",
    )

    sync_once(cline_store, session_factory)

    identities = {(event.provider_id, event.model_id) for event in stored_events(session_factory)}
    assert identities == {("cline", "shared-model"), ("openrouter", "shared-model")}


def test_a_record_written_after_the_checkpoint_is_picked_up_on_the_next_scan(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    cline_store.add_assistant_message(time_created_ms=FIRST_MS)

    sync_once(cline_store, session_factory)
    cline_store.add_assistant_message(time_created_ms=SECOND_MS)
    sync_once(cline_store, session_factory)

    with session_factory() as session:
        assert count_usage_events(session, "cline") == 2
    assert all_time_summary(session_factory) == 240


def test_a_message_file_rewritten_at_the_checkpoint_millisecond_is_re_read(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    # Cline rewrites the whole session file as a conversation grows, so two
    # messages can share a millisecond. Neither may be lost.
    cline_store.add_assistant_message(time_created_ms=FIRST_MS)
    sync_once(cline_store, session_factory)

    cline_store.add_assistant_message(message_id="msg_same_ms", time_created_ms=FIRST_MS)
    sync_once(cline_store, session_factory)

    with session_factory() as session:
        assert count_usage_events(session, "cline") == 2


def test_a_retried_call_keeps_the_failure_and_the_success_apart(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    # A rate-limited call is stored as unavailable so the gap is visible, and the
    # retry that succeeded is stored as its own reported event. Neither is
    # silently dropped and neither is counted twice.
    cline_store.add_error_message(session_id="ses_retry", time_created_ms=FIRST_MS)
    cline_store.add_assistant_message(
        session_id="ses_retry",
        message_id="msg_retry_ok",
        time_created_ms=SECOND_MS,
    )

    sync_once(cline_store, session_factory)

    statuses = {
        event.source_event_id.rsplit(":", 1)[1]: event.usage_status
        for event in stored_events(session_factory)
    }
    assert statuses == {"error_0001": "unavailable", "msg_retry_ok": "reported"}
    assert all_time_summary(session_factory) == 120


def test_a_subagent_session_is_attributed_to_its_own_session_and_model(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    # No live Cline store has subagent rows, so the collector cannot be verified
    # against them today. Attribution comes from each message's own modelInfo and
    # session id, which keeps working when a version does populate them.
    cline_store.add_assistant_message(session_id="ses_lead", message_id="msg_lead")
    cline_store.add_assistant_message(
        {"modelInfo": {"id": "cline-free/muse-spark-1.3-contributor", "provider": "cline"}},
        session_id="ses_sub",
        message_id="msg_sub",
        time_created_ms=SECOND_MS,
        is_subagent=True,
        parent_session_id="ses_lead",
    )

    sync_once(cline_store, session_factory)

    attribution = {
        (event.session_id, event.model_id) for event in stored_events(session_factory)
    }
    assert attribution == {
        ("ses_lead", "cline-free/gemini-3.8-flash"),
        ("ses_sub", "cline-free/muse-spark-1.3-contributor"),
    }


def test_a_resumed_session_copy_is_stored_separately_without_double_counting(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    # Resuming copies the earlier history: the same message id appears in both
    # sessions. Both are kept, so a later rule can supersede the failed run, and
    # re-scanning never adds them twice.
    cline_store.add_assistant_message(session_id="ses_failed", message_id="msg_shared")
    cline_store.add_assistant_message(session_id="ses_resumed", message_id="msg_shared")

    sync_once(cline_store, session_factory)
    sync_once(cline_store, session_factory)

    with session_factory() as session:
        assert count_usage_events(session, "cline") == 2
    assert all_time_summary(session_factory) == 240


def test_session_rollups_are_never_ingested_as_usage(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    # The envelope's metadata.usage repeats the per-message sums exactly. Reading
    # both would double every figure, so only the messages may be stored.
    cline_store.add_assistant_message()
    cline_store.write_session_rollup("ses_0001", input_tokens=100, output_tokens=20)

    sync_once(cline_store, session_factory)

    with session_factory() as session:
        assert count_usage_events(session, "cline") == 1
    assert all_time_summary(session_factory) == 120


def test_cache_and_reasoning_categories_never_inflate_the_per_call_total(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    # metrics carries cacheReadTokens alongside input and output. Folding it into
    # the per-call total would report 125 where the call itself cost 120.
    cline_store.add_assistant_message()

    sync_once(cline_store, session_factory)

    event = stored_events(session_factory)[0]
    assert event.total_tokens == 120
    assert event.cache_read_tokens == 5
    assert event.cache_overlap == "additive"
    assert event.consumption_tokens == 125


def test_missing_usage_is_stored_as_unknown_and_kept_out_of_totals(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    cline_store.add_assistant_message(session_id="ses_ok")
    cline_store.add_error_message(session_id="ses_ok", time_created_ms=SECOND_MS)

    sync_once(cline_store, session_factory)

    unavailable = [
        event for event in stored_events(session_factory) if event.usage_status == "unavailable"
    ]
    assert len(unavailable) == 1
    assert unavailable[0].input_tokens is None
    assert unavailable[0].total_tokens is None
    assert all_time_summary(session_factory) == 120


def test_raw_usage_is_preserved_for_future_compatibility(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    cline_store.add_assistant_message(
        message_overrides={"content": [{"type": "thinking"}, {"type": "text"}]}
    )

    sync_once(cline_store, session_factory)

    raw = stored_raw_usage(session_factory)
    assert raw["metrics"] == {
        "inputTokens": 100,
        "outputTokens": 20,
        "cacheReadTokens": 5,
        "cacheWriteTokens": 0,
    }
    assert raw["content_types"] == ["thinking", "text"]


def test_a_failed_call_records_its_own_error_and_keeps_the_checkpoint(
    cline_store: ClineStoreBuilder,
    session_factory: sessionmaker[Session],
) -> None:
    cline_store.add_assistant_message()
    sync_once(cline_store, session_factory)

    # The session file turns into something unreadable after the first run.
    messages_path = cline_store.sessions_dir / "ses_0001" / "ses_0001.messages.json"
    messages_path.write_text("{not json", encoding="utf-8")
    sync_once(cline_store, session_factory)

    with session_factory() as session:
        assert count_usage_events(session, "cline") == 1