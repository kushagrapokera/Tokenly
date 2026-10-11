"""Tests for the Cline collector's discovery, history, and incremental collection."""

import sqlite3
from pathlib import Path

import pytest

from collectors.cline import ClineCollector
from config.settings import Settings
from errors.exceptions import CollectorSourceUnreadableError
from tests.collectors.cline.conftest import ClineStoreBuilder

FIRST_MS = 1_790_495_317_187
SECOND_MS = 1_790_495_900_000


def collector_for(data_dir: Path) -> ClineCollector:
    """A collector pointed at a fixture data directory."""
    return ClineCollector(Settings(cline_data_dir=data_dir))


def test_discovery_reports_a_readable_store(cline_store: ClineStoreBuilder) -> None:
    cline_store.add_assistant_message()
    cline_store.add_assistant_message()

    result = collector_for(cline_store.data_dir).discover()

    assert result.platform == "cline"
    assert result.available is True
    assert result.source_path.endswith("sessions")
    assert "1 sessions" in result.detail
    assert "2 assistant messages" in result.detail


def test_discovery_reports_absent_instead_of_raising(tmp_path: Path) -> None:
    result = ClineCollector(Settings(cline_data_dir=tmp_path)).discover()

    assert result.available is False
    assert "no Cline sessions directory" in result.detail


def test_discovery_works_without_a_session_index(cline_store: ClineStoreBuilder) -> None:
    cline_store.add_assistant_message()
    cline_store.index_path.unlink()

    result = collector_for(cline_store.data_dir).discover()

    assert result.available is True
    assert "index absent" in result.detail


def test_collection_against_a_missing_store_raises_a_named_error(tmp_path: Path) -> None:
    collector = ClineCollector(Settings(cline_data_dir=tmp_path))

    with pytest.raises(CollectorSourceUnreadableError):
        collector.collect_history()


def test_history_returns_one_record_per_assistant_message(
    cline_store: ClineStoreBuilder,
) -> None:
    cline_store.add_assistant_message(time_created_ms=FIRST_MS)
    cline_store.add_assistant_message(time_created_ms=SECOND_MS)

    records = collector_for(cline_store.data_dir).collect_history()

    assert len(records) == 2
    assert [record.timestamp for record in records] == sorted(
        record.timestamp for record in records
    )


def test_user_messages_are_never_collected(cline_store: ClineStoreBuilder) -> None:
    cline_store.add_user_message()
    cline_store.add_assistant_message()

    records = collector_for(cline_store.data_dir).collect_history()

    assert len(records) == 1


def test_error_display_is_stored_as_unavailable(cline_store: ClineStoreBuilder) -> None:
    cline_store.add_assistant_message(
        message_overrides={
            "id": "error_0001",
            "content": [{"type": "text", "text": "limit reached"}],
            "modelInfo": {"id": "cline-free/gemini-3.8-flash", "provider": "cline"},
            "metadata": {"displayOnly": True, "displayRole": "error"},
        },
        message_id="error_0001",
    )
    _strip_metrics(cline_store, "ses_0001", "error_0001")

    records = collector_for(cline_store.data_dir).collect_history()

    assert len(records) == 1
    assert records[0].usage_status == "unavailable"
    assert records[0].total_tokens is None


def _strip_metrics(store: ClineStoreBuilder, session_id: str, message_id: str) -> None:
    """Remove the metrics block from one fixture message."""
    import json

    messages_path = store.sessions_dir / session_id / f"{session_id}.messages.json"
    payload = json.loads(messages_path.read_text(encoding="utf-8"))
    for message in payload["messages"]:
        if message["id"] == message_id:
            message.pop("metrics", None)
    messages_path.write_text(json.dumps(payload), encoding="utf-8")


def test_model_switching_attributes_each_record_to_its_own_model(
    cline_store: ClineStoreBuilder,
) -> None:
    cline_store.add_assistant_message(
        message_overrides={"modelInfo": {"id": "model-a", "provider": "cline"}}
    )
    cline_store.add_assistant_message(
        message_overrides={"modelInfo": {"id": "model-b", "provider": "cline"}}
    )

    records = collector_for(cline_store.data_dir).collect_history()

    assert sorted(record.model_id for record in records) == ["model-a", "model-b"]


def test_resume_duplicate_ids_stay_distinct_per_session(
    cline_store: ClineStoreBuilder,
) -> None:
    """Phase 1: the same msg id in two sessions must not collapse into one row."""
    cline_store.add_assistant_message(session_id="ses_0001", message_id="msg_dup")
    cline_store.add_assistant_message(session_id="ses_0002", message_id="msg_dup")

    records = collector_for(cline_store.data_dir).collect_history()

    assert len(records) == 2
    assert len({record.source_event_id for record in records}) == 2


def test_orphan_session_directory_is_collected_without_an_index_row(
    cline_store: ClineStoreBuilder,
) -> None:
    cline_store.add_assistant_message(session_id="ses_orphan", indexed=False)

    records = collector_for(cline_store.data_dir).collect_history()

    assert [record.session_id for record in records] == ["ses_orphan"]


def test_a_stale_index_path_still_collects_the_session(cline_store: ClineStoreBuilder) -> None:
    # Each session's file path is rebuilt from its id, so a `messages_path` left
    # empty or pointing elsewhere by a Cline version cannot hide real usage.
    cline_store.add_assistant_message()
    with sqlite3.connect(cline_store.index_path) as connection:
        connection.execute("UPDATE sessions SET messages_path = '/gone/missing.json'")

    records = collector_for(cline_store.data_dir).collect_history()

    assert [record.session_id for record in records] == ["ses_0001"]


def test_updates_resume_from_a_checkpoint(cline_store: ClineStoreBuilder) -> None:
    cline_store.add_assistant_message(time_created_ms=FIRST_MS)
    cline_store.add_assistant_message(time_created_ms=SECOND_MS)
    collector = collector_for(cline_store.data_dir)

    records = collector.collect_updates(str(FIRST_MS))

    assert [record.timestamp for record in records]
    assert all(int(record.timestamp.timestamp() * 1000) >= FIRST_MS for record in records)


def test_scan_reports_no_pending_messages(cline_store: ClineStoreBuilder) -> None:
    cline_store.add_assistant_message()

    outcome = collector_for(cline_store.data_dir).collect_scan(None)

    assert len(outcome.records) == 1
    assert outcome.pending_timestamps_ms == []


def test_collecting_never_modifies_the_source_files(
    cline_store: ClineStoreBuilder,
) -> None:
    cline_store.add_assistant_message()
    messages_path = cline_store.sessions_dir / "ses_0001" / "ses_0001.messages.json"
    before = messages_path.read_bytes()

    collector_for(cline_store.data_dir).collect_history()

    assert messages_path.read_bytes() == before


def test_a_malformed_record_does_not_abort_the_whole_scan(
    cline_store: ClineStoreBuilder,
) -> None:
    cline_store.add_assistant_message(message_id="msg_good")
    cline_store.add_assistant_message(
        message_overrides={"modelInfo": {"id": "", "provider": "cline"}},
        message_id="msg_bad",
    )

    records = collector_for(cline_store.data_dir).collect_history()

    assert [record.message_id for record in records] == ["msg_good"]


def test_an_injected_extractor_can_filter_records(
    cline_store: ClineStoreBuilder,
) -> None:
    from collectors.cline.extractor import extract_usage_record
    from collectors.cline.reader import MessageRow
    from schemas.usage import UsageRecord

    cline_store.add_assistant_message(
        message_overrides={"modelInfo": {"id": "keep", "provider": "cline"}}
    )
    cline_store.add_assistant_message(
        message_overrides={"modelInfo": {"id": "drop", "provider": "cline"}}
    )

    def only_keep(row: MessageRow) -> UsageRecord | None:
        record = extract_usage_record(row)
        if record is None or record.model_id != "keep":
            return None
        return record

    collector = ClineCollector(
        Settings(cline_data_dir=cline_store.data_dir), record_extractor=only_keep
    )

    assert [record.model_id for record in collector.collect_history()] == ["keep"]


def test_the_collector_reports_its_platform() -> None:
    assert ClineCollector().platform == "cline"
