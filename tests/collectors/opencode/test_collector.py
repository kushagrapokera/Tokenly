"""Tests for the OpenCode collector's discovery, history, and incremental collection."""

import subprocess
from pathlib import Path

import pytest

from collectors.opencode import OpenCodeCollector
from collectors.opencode.extractor import extract_usage_record
from collectors.opencode.reader import MessageRow, open_snapshot
from collectors.opencode.snapshot import snapshot_database
from config.settings import Settings
from errors.exceptions import CollectorSourceUnreadableError
from schemas.usage import UsageRecord
from tests.collectors.opencode.conftest import OpenCodeDatabaseBuilder

FIRST_MS = 1_700_000_000_000
SECOND_MS = 1_700_000_600_000


@pytest.fixture(autouse=True)
def never_call_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test off the real machine's OpenCode install."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="not found"
        ),
    )


def collector_for(database_path: Path) -> OpenCodeCollector:
    """A collector pointed at a fixture database directory."""
    settings = Settings(opencode_data_dir=database_path.parent)
    return OpenCodeCollector(settings)


def test_discovery_reports_a_readable_database(opencode_db: OpenCodeDatabaseBuilder) -> None:
    opencode_db.add_assistant_message()
    opencode_db.add_assistant_message()

    result = collector_for(opencode_db.path).discover()

    assert result.platform == "opencode"
    assert result.available is True
    assert result.storage_format == "sqlite"
    assert result.source_path.endswith("opencode.db")
    assert "2 assistant messages" in result.detail


def test_discovery_reports_absent_instead_of_raising(tmp_path: Path) -> None:
    result = OpenCodeCollector(Settings(opencode_data_dir=tmp_path)).discover()

    assert result.available is False
    assert "no OpenCode database file" in result.detail


def test_discovery_reports_unavailable_when_the_file_is_not_a_database(tmp_path: Path) -> None:
    (tmp_path / "opencode.db").write_bytes(b"this is not a sqlite file")

    result = OpenCodeCollector(Settings(opencode_data_dir=tmp_path)).discover()

    assert result.available is False
    assert result.detail


def test_collection_against_a_missing_database_raises_a_named_error(tmp_path: Path) -> None:
    collector = OpenCodeCollector(Settings(opencode_data_dir=tmp_path))

    with pytest.raises(CollectorSourceUnreadableError):
        collector.collect_history()


def test_history_returns_one_record_per_completed_assistant_message(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    opencode_db.add_assistant_message(time_created_ms=FIRST_MS)
    opencode_db.add_assistant_message(time_created_ms=SECOND_MS)

    records = collector_for(opencode_db.path).collect_history()

    assert len(records) == 2
    assert [record.timestamp for record in records] == sorted(
        record.timestamp for record in records
    )


def test_an_in_flight_message_is_left_for_a_later_scan(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    opencode_db.add_assistant_message(message_id="msg_done", time_created_ms=FIRST_MS)
    opencode_db.add_assistant_message(
        message_id="msg_live",
        message_overrides={"time": {"created": SECOND_MS}},
        time_created_ms=SECOND_MS,
    )

    records = collector_for(opencode_db.path).collect_history()

    assert [record.message_id for record in records] == ["msg_done"]


def test_the_message_that_finishes_appears_on_the_next_scan(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    """The exact scenario the checkpoint millisecond rule exists for."""
    collector = collector_for(opencode_db.path)
    opencode_db.add_assistant_message(
        message_id="msg_live",
        time_created_ms=FIRST_MS,
        message_overrides={"time": {"created": FIRST_MS}},
    )
    assert collector.collect_history() == []

    opencode_db.update_message(
        "msg_live",
        {
            "role": "assistant",
            "providerID": "opencode",
            "modelID": "m",
            "tokens": {"input": 5, "output": 5},
            "time": {"created": FIRST_MS, "completed": FIRST_MS + 1},
        },
    )

    records = collector.collect_updates(str(FIRST_MS))

    assert [record.message_id for record in records] == ["msg_live"]


def test_updates_return_only_messages_after_the_checkpoint(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    """A checkpoint one millisecond past the old message leaves only the new one."""
    opencode_db.add_assistant_message(message_id="msg_old", time_created_ms=FIRST_MS)
    opencode_db.add_assistant_message(message_id="msg_new", time_created_ms=SECOND_MS)

    records = collector_for(opencode_db.path).collect_updates(str(FIRST_MS + 1))

    assert [record.message_id for record in records] == ["msg_new"]


def test_a_checkpoint_at_the_old_messages_millisecond_re_reads_it(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    """Deliberate: the message may have been still generating at the previous scan."""
    opencode_db.add_assistant_message(message_id="msg_old", time_created_ms=FIRST_MS)
    opencode_db.add_assistant_message(message_id="msg_new", time_created_ms=SECOND_MS)

    records = collector_for(opencode_db.path).collect_updates(str(FIRST_MS))

    assert [record.message_id for record in records] == ["msg_old", "msg_new"]


def test_updates_without_a_checkpoint_collect_everything(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    opencode_db.add_assistant_message(time_created_ms=FIRST_MS)
    opencode_db.add_assistant_message(time_created_ms=SECOND_MS)

    collector = collector_for(opencode_db.path)

    assert len(collector.collect_updates(None)) == len(collector.collect_history())


def test_history_and_updates_agree_on_a_fresh_database(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    for index in range(5):
        opencode_db.add_assistant_message(time_created_ms=FIRST_MS + index * 1000)

    collector = collector_for(opencode_db.path)

    assert collector.collect_updates(None) == collector.collect_history()


def test_collecting_never_modifies_the_source_database(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    opencode_db.add_assistant_message()
    before = opencode_db.path.read_bytes()

    collector_for(opencode_db.path).collect_history()

    assert opencode_db.path.read_bytes() == before


def test_every_record_is_keyed_by_its_own_message_id(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    for index in range(3):
        opencode_db.add_assistant_message(
            message_id=f"msg_{index}", message_overrides={"parentID": "msg_shared"}
        )

    records = collector_for(opencode_db.path).collect_history()

    assert [record.source_event_id for record in records] == ["msg_0", "msg_1", "msg_2"]
    assert len({record.source_event_id for record in records}) == 3


def test_a_malformed_record_does_not_abort_the_whole_scan(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    opencode_db.add_assistant_message(message_id="msg_good")
    opencode_db.add_message({"role": "assistant"}, message_id="msg_no_identity")

    records = collector_for(opencode_db.path).collect_history()

    assert [record.message_id for record in records] == ["msg_good"]


def test_an_injected_extractor_can_filter_records(opencode_db: OpenCodeDatabaseBuilder) -> None:
    opencode_db.add_assistant_message(message_overrides={"modelID": "keep"})
    opencode_db.add_assistant_message(message_overrides={"modelID": "drop"})

    def only_keep(row: MessageRow) -> UsageRecord | None:
        record = extract_usage_record(row)
        if record is None or record.model_id != "keep":
            return None
        return record

    collector = OpenCodeCollector(
        Settings(opencode_data_dir=opencode_db.path.parent), record_extractor=only_keep
    )

    assert [record.model_id for record in collector.collect_history()] == ["keep"]


def test_collection_survives_a_database_with_only_a_session_row(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    assert collector_for(opencode_db.path).collect_history() == []


def test_the_collector_reports_its_platform() -> None:
    assert OpenCodeCollector().platform == "opencode"


def test_reading_a_snapshot_works_through_sqlite_backup(
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    """The snapshot must be a real, queryable database, not a byte copy of a WAL file."""
    opencode_db.add_assistant_message()

    with snapshot_database(opencode_db.path) as snapshot_path:
        connection = open_snapshot(snapshot_path)
        try:
            assert connection.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 1
        finally:
            connection.close()
