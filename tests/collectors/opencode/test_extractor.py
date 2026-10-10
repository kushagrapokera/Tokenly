"""Tests for turning raw OpenCode message rows into normalized usage records."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from collectors.opencode.extractor import (
    MalformedMessageError,
    extract_usage_record,
    is_completed,
)
from collectors.opencode.reader import (
    MessageRow,
    count_assistant_messages,
    iter_assistant_messages,
    open_snapshot,
)
from collectors.opencode.snapshot import snapshot_database
from tests.collectors.opencode.conftest import OpenCodeDatabaseBuilder

CREATED_MS = 1_789_532_819_792
COMPLETED_MS = 1_789_532_824_807


def make_row(data: dict[str, object], message_id: str = "msg_0001") -> MessageRow:
    """Build a MessageRow without needing a database."""
    return MessageRow(
        message_id=message_id,
        session_id="ses_0001",
        time_created_ms=CREATED_MS,
        data=data,
    )


def assistant_message(**overrides: object) -> dict[str, object]:
    """A minimal complete assistant message payload."""
    message: dict[str, object] = {
        "role": "assistant",
        "providerID": "opencode",
        "modelID": "big-pickle",
        "tokens": {
            "total": 8297,
            "input": 6478,
            "output": 27,
            "reasoning": 0,
            "cache": {"read": 1792, "write": 0},
        },
        "time": {"created": CREATED_MS, "completed": COMPLETED_MS},
        "finish": "stop",
    }
    message.update(overrides)
    return message


def test_record_carries_provider_model_and_message_identity() -> None:
    row = make_row(assistant_message())

    record = extract_usage_record(row)

    assert record is not None
    assert record.platform == "opencode"
    assert record.provider_id == "opencode"
    assert record.model_id == "big-pickle"
    assert record.session_id == "ses_0001"
    assert record.message_id == "msg_0001"


def test_source_event_id_is_the_message_id() -> None:
    """Phase 1: message.id is the stable dedup key, not parentID."""
    row = make_row(assistant_message(parentID="msg_shared_parent"))

    record = extract_usage_record(row)

    assert record is not None
    assert record.source_event_id == "msg_0001"
    assert record.source_event_id != "msg_shared_parent"


def test_total_ignores_the_reported_total_and_sums_input_and_output() -> None:
    """OpenCode's total folds in reasoning and cache; only input+output may be summed."""
    row = make_row(assistant_message())

    record = extract_usage_record(row)

    assert record is not None
    assert record.input_tokens == 6478
    assert record.output_tokens == 27
    assert record.total_tokens == 6505
    assert record.total_tokens != 8297


def test_reported_total_is_preserved_for_later_phases() -> None:
    row = make_row(assistant_message())

    record = extract_usage_record(row)

    assert record is not None
    assert record.raw_usage["reported_total"] == 8297
    assert record.raw_usage["tokens"] == row.data["tokens"]


def test_timestamp_is_read_from_the_json_created_field_in_utc() -> None:
    row = make_row(assistant_message())

    record = extract_usage_record(row)

    assert record is not None
    assert record.timestamp == datetime(2026, 9, 16, 4, 26, 59, 792000, tzinfo=timezone.utc)


def test_timestamp_falls_back_to_the_row_column_when_json_lacks_created() -> None:
    row = make_row(assistant_message(time={"completed": COMPLETED_MS}))

    record = extract_usage_record(row)

    assert record is not None
    assert record.timestamp == datetime.fromtimestamp(CREATED_MS / 1000, tz=timezone.utc)


def test_variant_is_kept_as_metadata_rather_than_identity() -> None:
    row = make_row(assistant_message(variant="xhigh"))

    record = extract_usage_record(row)

    assert record is not None
    assert record.model_id == "big-pickle"
    assert record.raw_usage["variant"] == "xhigh"


def test_aborted_message_is_reported_as_zero_tokens_not_missing() -> None:
    """Phase 1: an aborted call completed, so its zeros are real, not absent."""
    row = make_row(
        assistant_message(
            tokens={"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}},
            error={"name": "MessageAbortedError"},
        )
    )

    record = extract_usage_record(row)

    assert record is not None
    assert record.input_tokens == 0
    assert record.output_tokens == 0
    assert record.usage_status == "reported"
    assert record.raw_usage["error"] == "MessageAbortedError"


def test_missing_finish_reason_still_counts_normally() -> None:
    row = make_row({k: v for k, v in assistant_message().items() if k != "finish"})

    record = extract_usage_record(row)

    assert record is not None
    assert record.usage_status == "reported"
    assert record.raw_usage["finish"] is None


def test_message_without_a_tokens_object_is_marked_unavailable() -> None:
    payload = assistant_message()
    del payload["tokens"]
    row = make_row(payload)

    record = extract_usage_record(row)

    assert record is not None
    assert record.usage_status == "unavailable"
    assert record.input_tokens is None
    assert record.output_tokens is None
    assert record.total_tokens is None


def test_missing_single_token_count_leaves_totals_unknown() -> None:
    row = make_row(assistant_message(tokens={"input": 6478, "output": 27}))

    record = extract_usage_record(row)

    assert record is not None
    assert record.input_tokens == 6478
    assert record.output_tokens == 27
    assert record.total_tokens == 6505


def test_negative_token_count_is_rejected_rather_than_stored() -> None:
    row = make_row(assistant_message(tokens={"input": -5, "output": 27}))

    record = extract_usage_record(row)

    assert record is not None
    assert record.input_tokens is None
    assert record.total_tokens is None


def test_boolean_token_count_is_not_treated_as_an_integer() -> None:
    row = make_row(assistant_message(tokens={"input": True, "output": 27}))

    record = extract_usage_record(row)

    assert record is not None
    assert record.input_tokens is None


def test_non_object_tokens_value_is_treated_as_unavailable() -> None:
    row = make_row(assistant_message(tokens="not-an-object"))

    record = extract_usage_record(row)

    assert record is not None
    assert record.usage_status == "unavailable"


def test_in_flight_message_yields_no_record() -> None:
    """A message with no `completed` is still generating; it waits for a later scan."""
    row = make_row(assistant_message(time={"created": CREATED_MS}))

    assert is_completed(row) is False
    assert extract_usage_record(row) is None


@pytest.mark.parametrize("missing_field", ["providerID", "modelID"])
def test_missing_identity_field_raises_a_named_error(missing_field: str) -> None:
    payload = assistant_message()
    del payload[missing_field]
    row = make_row(payload)

    with pytest.raises(MalformedMessageError) as caught:
        extract_usage_record(row)

    assert caught.value.missing_field == missing_field
    assert caught.value.message_id == "msg_0001"


@contextmanager
def reader_for(database_path: Path) -> Iterator[sqlite3.Connection]:
    """Open the fixture database the same way the collector does."""
    connection = open_snapshot(database_path)
    try:
        yield connection
    finally:
        connection.close()


def test_records_survive_a_round_trip_through_the_reader(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    opencode_db.add_assistant_message()
    opencode_db.add_assistant_message(message_overrides={"modelID": "union-alpha"})

    with reader_for(opencode_db.path) as connection:
        records = [extract_usage_record(row) for row in iter_assistant_messages(connection)]

    assert records[0] is not None and records[0].model_id == "space-bunny-free"
    assert records[1] is not None and records[1].model_id == "union-alpha"


def test_reader_skips_rows_whose_json_is_corrupt(opencode_db: OpenCodeDatabaseBuilder) -> None:
    opencode_db.add_assistant_message()
    opencode_db.add_message({}, raw_data="{not valid json")

    with reader_for(opencode_db.path) as connection:
        rows = list(iter_assistant_messages(connection))

    assert len(rows) == 1


def test_reader_ignores_user_messages(opencode_db: OpenCodeDatabaseBuilder) -> None:
    opencode_db.add_message({"role": "user", "time": {"created": CREATED_MS}})

    with reader_for(opencode_db.path) as connection:
        rows = list(iter_assistant_messages(connection))

    assert rows == []


def test_snapshot_never_writes_to_the_source_file(opencode_db: OpenCodeDatabaseBuilder) -> None:
    """The live database must come out of a snapshot byte-for-byte unchanged."""
    opencode_db.add_assistant_message()
    before = Path(opencode_db.path).read_bytes()

    with snapshot_database(opencode_db.path) as snapshot_path:
        connection = open_snapshot(snapshot_path)
        try:
            assert count_assistant_messages(connection) == 1
        finally:
            connection.close()

    assert Path(opencode_db.path).read_bytes() == before


def test_snapshot_directory_is_removed_after_use(opencode_db: OpenCodeDatabaseBuilder) -> None:
    opencode_db.add_assistant_message()

    with snapshot_database(opencode_db.path) as snapshot_path:
        snapshot_directory = snapshot_path.parent
        assert snapshot_directory.is_dir()

    assert not snapshot_directory.exists()
