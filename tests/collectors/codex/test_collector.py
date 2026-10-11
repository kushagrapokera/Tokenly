"""Tests for the Codex collector's discovery, filtering, rollup exclusion, and checkpoints."""

from pathlib import Path

import pytest

from collectors.codex import CodexCollector
from collectors.codex.collector import STORAGE_FORMAT
from config.settings import Settings
from errors.exceptions import CollectorSourceUnreadableError
from tests.collectors.codex.conftest import (
    MODEL_DEFAULT,
    PROVIDER_DEFAULT,
    CodexStoreBuilder,
)


def collector_for(store: CodexStoreBuilder) -> CodexCollector:
    """A collector pointed at a fixture Codex home."""
    return CodexCollector(Settings(codex_home=store.codex_home))


# --- discovery ---


def test_discovery_reports_a_readable_store(codex_store: CodexStoreBuilder) -> None:
    codex_store.add_usage_call()

    result = collector_for(codex_store).discover()

    assert result.platform == "codex"
    assert result.available is True
    assert result.source_path.endswith("sessions")
    assert "rollout session files" in result.detail
    assert result.storage_format == STORAGE_FORMAT


def test_discovery_reports_absent_instead_of_raising(tmp_path: Path) -> None:
    result = CodexCollector(Settings(codex_home=tmp_path / "nowhere")).discover()

    assert result.available is False
    assert "no Codex sessions directory" in result.detail


def test_discovery_reports_an_empty_sessions_directory(codex_store: CodexStoreBuilder) -> None:
    codex_store.sessions_dir.mkdir(parents=True, exist_ok=True)

    result = collector_for(codex_store).discover()

    assert result.available is False
    assert "no rollout session files" in result.detail


def test_collection_against_a_missing_store_raises_a_named_error(tmp_path: Path) -> None:
    collector = CodexCollector(Settings(codex_home=tmp_path / "void"))

    with pytest.raises(CollectorSourceUnreadableError):
        collector.collect_history()


# --- filtering: only per-call token_usage_record is collected ---


def test_the_token_count_event_is_never_collected(codex_store: CodexStoreBuilder) -> None:
    """The `event_msg`/`token_count` echo must not become a second record."""
    codex_store.add_usage_call(input_tokens=100, output_tokens=20)
    codex_store.add_token_count_event(input_tokens=100, output_tokens=20)

    records = collector_for(codex_store).collect_history()

    assert len(records) == 1
    assert records[0].total_tokens == 120


def test_turn_and_thread_rollups_are_never_summed(codex_store: CodexStoreBuilder) -> None:
    """`turn_token_usage`/`thread_token_usage` repeat the per-call sums — one turn, two calls."""
    codex_store.add_usage_call(input_tokens=100, output_tokens=20)
    codex_store.add_usage_call(input_tokens=50, output_tokens=10)

    records = collector_for(codex_store).collect_history()

    assert len(records) == 2
    # Sum of the per-call usage only: 120 + 60 = 180, not the rollup multiples.
    assert sum(record.total_tokens or 0 for record in records) == 180


def test_distinct_calls_stay_separate(codex_store: CodexStoreBuilder) -> None:
    codex_store.add_usage_call()
    codex_store.add_usage_call(input_tokens=50, output_tokens=10)

    records = collector_for(codex_store).collect_history()

    assert len(records) == 2


def test_the_same_response_id_in_two_sessions_does_not_collapse(
    codex_store: CodexStoreBuilder,
) -> None:
    first = "session-aaaa-0001"
    second = "session-bbbb-0002"
    codex_store.add_usage_call(session_id=first, response_id="dup-0001")
    codex_store.add_usage_call(session_id=second, response_id="dup-0001")

    records = collector_for(codex_store).collect_history()

    assert len(records) == 2
    assert {record.session_id for record in records} == {first, second}


def test_a_corrupt_line_does_not_abort_the_whole_scan(codex_store: CodexStoreBuilder) -> None:
    codex_store.add_usage_call(response_id="resp-good001")
    codex_store.append_corrupt_line()
    codex_store.add_usage_call(response_id="resp-good002")

    records = collector_for(codex_store).collect_history()

    assert len(records) == 2


def test_a_usageless_token_record_is_stored_as_unavailable(
    codex_store: CodexStoreBuilder,
) -> None:
    """A completed record carrying no usage object is unknown, not zero."""
    codex_store.add_usageless_call()

    records = collector_for(codex_store).collect_history()

    assert len(records) == 1
    assert records[0].usage_status == "unavailable"
    assert records[0].total_tokens is None


# --- model/provider join through the whole collector ---


def test_model_and_provider_are_joined_onto_every_record(
    codex_store: CodexStoreBuilder,
) -> None:
    codex_store.add_usage_call()

    records = collector_for(codex_store).collect_history()

    assert {record.model_id for record in records} == {MODEL_DEFAULT}
    assert {record.provider_id for record in records} == {PROVIDER_DEFAULT}


def test_a_call_whose_turn_has_no_context_keeps_its_usage_but_unknown_model(
    codex_store: CodexStoreBuilder,
) -> None:
    codex_store.add_usage_call(turn_id="turn-without-context", write_turn_context=False)

    records = collector_for(codex_store).collect_history()

    assert len(records) == 1
    assert records[0].model_id == "unknown"
    assert records[0].total_tokens == 120


# --- checkpointing and scans ---


def test_updates_resume_from_a_checkpoint(codex_store: CodexStoreBuilder) -> None:
    codex_store.add_usage_call(timestamp="2026-09-22T12:00:00.000Z", response_id="resp-early")
    collector = collector_for(codex_store)

    from datetime import datetime, timezone

    request_ms = int(datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)

    # A checkpoint strictly after the event's millisecond filters it out.
    assert collector.collect_updates(str(request_ms + 1)) == []
    # Resuming from (or before) the event's timestamp re-reads it; `covers` is strict.
    assert len(collector.collect_updates(str(request_ms))) == 1


def test_scan_reports_no_pending_messages(codex_store: CodexStoreBuilder) -> None:
    codex_store.add_usage_call()

    outcome = collector_for(codex_store).collect_scan(None)

    assert len(outcome.records) == 1
    assert outcome.pending_timestamps_ms == []


def test_the_collector_reports_its_platform() -> None:
    assert CodexCollector().platform == "codex"
