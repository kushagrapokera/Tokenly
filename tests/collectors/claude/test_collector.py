"""Tests for the Claude collector's discovery, collapse, and incremental collection."""

import json
from pathlib import Path

import pytest

from collectors.claude import ClaudeCodeCollector
from config.settings import Settings
from errors.exceptions import CollectorSourceUnreadableError
from tests.collectors.claude.conftest import SES_DEFAULT_ID, ClaudeStoreBuilder


def collector_for(store: ClaudeStoreBuilder) -> ClaudeCodeCollector:
    """A collector pointed at a fixture projects directory."""
    return ClaudeCodeCollector(Settings(claude_data_dir=store.projects_dir.parent))


# --- discovery ---


def test_discovery_reports_a_readable_store(claude_store: ClaudeStoreBuilder) -> None:
    claude_store.add_assistant_request(line_count=1)

    result = collector_for(claude_store).discover()

    assert result.platform == "claude_code"
    assert result.available is True
    assert result.source_path.endswith("projects")
    assert "1 session transcripts" in result.detail


def test_discovery_reports_absent_instead_of_raising(tmp_path: Path) -> None:
    result = ClaudeCodeCollector(Settings(claude_data_dir=tmp_path / "nowhere")).discover()

    assert result.available is False
    assert "no Claude Code projects directory" in result.detail


def test_discovery_reports_an_empty_projects_directory(claude_store: ClaudeStoreBuilder) -> None:
    result = collector_for(claude_store).discover()

    assert result.available is False
    assert "no session transcripts" in result.detail


def test_collection_against_a_missing_store_raises_a_named_error(tmp_path: Path) -> None:
    collector = ClaudeCodeCollector(Settings(claude_data_dir=tmp_path / "void"))

    with pytest.raises(CollectorSourceUnreadableError):
        collector.collect_history()


# --- repeated message lines collapse to one request ---


def test_repeated_lines_of_one_request_collapse_to_one_record(
    claude_store: ClaudeStoreBuilder,
) -> None:
    claude_store.add_assistant_request(line_count=5, input_tokens=100, output_tokens=20)

    records = collector_for(claude_store).collect_history()

    assert len(records) == 1
    assert records[0].total_tokens == 120  # not 5 * 120


def test_distinct_requests_in_one_session_stay_separate(
    claude_store: ClaudeStoreBuilder,
) -> None:
    claude_store.add_assistant_request(line_count=2)
    claude_store.add_assistant_request(line_count=3, input_tokens=50, output_tokens=10)

    records = collector_for(claude_store).collect_history()

    assert len(records) == 2
    assert sorted(record.total_tokens or 0 for record in records) == [60, 120]


def test_the_same_message_id_in_two_sessions_does_not_collapse(
    claude_store: ClaudeStoreBuilder,
) -> None:
    """Resumed sessions copy history into new files; session namespacing keeps them."""
    first = "f1111111-2222-4333-8444-555555555555"
    second = "a9999999-8888-4777-8666-777777777777"
    claude_store.add_assistant_request(session_id=first, message_id="dup-0001", line_count=1)
    claude_store.add_assistant_request(session_id=second, message_id="dup-0001", line_count=1)

    records = collector_for(claude_store).collect_history()

    assert len(records) == 2
    assert {record.session_id for record in records} == {first, second}


# --- filtering and field mapping through the whole collector ---


def test_user_lines_and_cost_state_are_never_collected(
    claude_store: ClaudeStoreBuilder,
) -> None:
    claude_store.add_user_line()
    claude_store.add_assistant_request(line_count=1)
    claude_store.write_cost_state(input_tokens=999, output_tokens=999)

    records = collector_for(claude_store).collect_history()

    assert len(records) == 1
    assert records[0].total_tokens == 120  # not the cost-state's 999+999


def test_model_switching_attributes_each_request_to_its_own_model(
    claude_store: ClaudeStoreBuilder,
) -> None:
    claude_store.add_assistant_request(
        message_id="m-0000001", model="claude-sonnet-4-5", line_count=1
    )
    claude_store.add_assistant_request(
        message_id="m-0000002", model="deepseek/deepseek-chat", line_count=1
    )

    records = collector_for(claude_store).collect_history()

    assert {record.model_id for record in records} == {
        "claude-sonnet-4-5",
        "deepseek/deepseek-chat",
    }
    deepseek_records = [r for r in records if r.model_id == "deepseek/deepseek-chat"]
    assert deepseek_records[0].provider_id == "deepseek"


def test_sidechain_lines_are_collected_like_any_other_request(
    claude_store: ClaudeStoreBuilder,
) -> None:
    """Subagent (sidechain) calls are real model usage; plan §4.4 counts them once."""
    claude_store.add_assistant_request(line_count=1, sidechain=True)

    records = collector_for(claude_store).collect_history()

    assert len(records) == 1


def test_a_corrupt_line_does_not_abort_the_whole_scan(
    claude_store: ClaudeStoreBuilder,
) -> None:
    claude_store.add_assistant_request(message_id="m-good001", line_count=1)
    claude_store.append_corrupt_line()
    claude_store.add_assistant_request(message_id="m-good002", line_count=1)

    records = collector_for(claude_store).collect_history()

    assert len(records) == 2


def test_a_usageless_assistant_line_is_stored_as_unavailable(
    claude_store: ClaudeStoreBuilder,
) -> None:
    """A completed assistant line carrying no usage object is unknown, not zero."""
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "id": "m-nousage",
                "role": "assistant",
                "model": "claude-sonnet-4-5",
            },
            "timestamp": "2026-09-22T11:52:31.580Z",
            "sessionId": SES_DEFAULT_ID,
        }
    )
    transcript = claude_store.add_session(SES_DEFAULT_ID)
    transcript.write_text(line + "\n", encoding="utf-8")

    records = collector_for(claude_store).collect_history()

    assert len(records) == 1
    assert records[0].usage_status == "unavailable"
    assert records[0].total_tokens is None
    assert records[0].input_tokens is None


# --- checkpointing and scans ---


def test_updates_resume_from_a_checkpoint(claude_store: ClaudeStoreBuilder) -> None:
    claude_store.add_assistant_request(
        message_id="m-early001",
        timestamp="2026-09-22T11:00:00.000Z",
        line_count=1,
    )
    collector = collector_for(claude_store)

    # A checkpoint strictly after the request's own millisecond filters it out.
    from datetime import datetime, timezone

    request_ms = int(
        datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc).timestamp() * 1000
    )
    records = collector.collect_updates(str(request_ms + 1))

    assert records == []

    # Resuming from before (or at) the request's timestamp collects it. The
    # checkpoint's own millisecond is re-read, matching `Checkpoint.covers`.
    assert len(collector.collect_updates(str(request_ms))) == 1


def test_scan_reports_no_pending_messages(claude_store: ClaudeStoreBuilder) -> None:
    claude_store.add_assistant_request(line_count=3)

    outcome = collector_for(claude_store).collect_scan(None)

    assert len(outcome.records) == 1
    assert outcome.pending_timestamps_ms == []


def test_the_collector_reports_its_platform() -> None:
    assert ClaudeCodeCollector().platform == "claude_code"
