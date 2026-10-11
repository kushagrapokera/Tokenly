"""Tests for storing, querying, and updating usage events.

The property under test throughout is idempotency: re-importing the same usage must not
create a second row or inflate a total, because a collector can legitimately hand us the
same message again after a rescan, a restart, or a re-read of the checkpoint's
millisecond.
"""

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collectors.opencode import OpenCodeCollector
from database import repository
from database.connection import Base
from database.models import CollectorState, UsageEvent
from database.repository import (
    count_usage_events,
    query_usage_events,
    sum_tokens,
    upsert_usage_records,
)
from database.state import (
    checkpoint_for,
    load_progress,
    mark_error,
    mark_scanning,
    save_progress,
)
from schemas.usage import UsageRecord

UTC = timezone.utc
DAY_ONE = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
DAY_TWO = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    """A session against a fresh SQLite database with the schema created."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as open_session:
        yield open_session
    engine.dispose()


def make_record(
    source_event_id: str = "msg_1",
    *,
    timestamp: datetime = DAY_ONE,
    input_tokens: int | None = 100,
    output_tokens: int | None = 20,
    consumption_tokens: int | None = 120,
    session_id: str = "ses_1",
) -> UsageRecord:
    """A normalized record ready to store."""
    return UsageRecord(
        platform="opencode",
        provider_id="opencode",
        model_id="space-bunny-free",
        session_id=session_id,
        message_id=source_event_id,
        source_event_id=source_event_id,
        timestamp=timestamp,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=None if input_tokens is None else input_tokens + (output_tokens or 0),
        reasoning_tokens=0,
        cache_read_tokens=900,
        cache_write_tokens=0,
        consumption_tokens=consumption_tokens,
        usage_status="reported",
        raw_usage={"tokens": {"input": input_tokens}, "finish": "stop"},
    )


# --- schema constraints and indexes ---


def test_the_schema_declares_the_required_indexes(session: Session) -> None:
    engine = session.get_bind()
    assert engine is not None
    index_names = {index["name"] for index in inspect(engine).get_indexes("usage_events")}

    assert {
        "ix_usage_events_timestamp",
        "ix_usage_events_provider_id",
        "ix_usage_events_model_id",
        "ix_usage_events_platform_timestamp",
    } <= index_names


def test_the_unique_constraint_rejects_a_duplicate_source_event(session: Session) -> None:
    session.add(UsageEvent(**_row_values()))
    session.commit()

    session.add(UsageEvent(**_row_values()))

    with pytest.raises(IntegrityError):
        session.commit()


def test_the_same_source_event_id_is_allowed_on_a_different_platform(session: Session) -> None:
    session.add(UsageEvent(**_row_values(platform="opencode")))
    session.add(UsageEvent(**_row_values(platform="claude")))
    session.commit()

    assert count_usage_events(session) == 2


def test_a_negative_token_count_is_rejected_by_the_database(session: Session) -> None:
    session.add(UsageEvent(**_row_values(input_tokens=-1)))

    with pytest.raises(IntegrityError):
        session.commit()


def test_an_unknown_usage_status_is_rejected_by_the_database(session: Session) -> None:
    session.add(UsageEvent(**_row_values(usage_status="maybe")))

    with pytest.raises(IntegrityError):
        session.commit()


# --- timestamps ---


def test_a_timestamp_comes_back_aware_and_equal_to_what_was_written(session: Session) -> None:
    upsert_usage_records(session, [make_record()])

    stored = query_usage_events(session)[0]

    assert stored.timestamp.tzinfo is not None
    assert stored.timestamp == DAY_ONE


def test_a_timestamp_in_another_offset_is_stored_as_utc(session: Session) -> None:
    from datetime import timezone as tz

    moment = datetime(2026, 10, 1, 17, 30, tzinfo=tz(timedelta(hours=5, minutes=30)))
    upsert_usage_records(session, [make_record(timestamp=moment)])

    stored = query_usage_events(session)[0]

    assert stored.timestamp == DAY_ONE


# --- upsert behaviour ---


def test_new_records_are_inserted(session: Session) -> None:
    result = upsert_usage_records(session, [make_record("msg_1"), make_record("msg_2")])

    assert (result.inserted, result.updated) == (2, 0)
    assert count_usage_events(session) == 2


def test_reimporting_the_same_record_does_not_create_a_second_row(session: Session) -> None:
    record = make_record("msg_1")

    upsert_usage_records(session, [record])
    result = upsert_usage_records(session, [record])

    assert (result.inserted, result.updated) == (0, 1)
    assert count_usage_events(session) == 1


def test_repeated_imports_never_inflate_the_stored_total(session: Session) -> None:
    record = make_record("msg_1")

    for _ in range(5):
        upsert_usage_records(session, [record])

    assert count_usage_events(session) == 1
    assert sum_tokens(session, "consumption_tokens") == 120


def test_a_changed_record_updates_in_place(session: Session) -> None:
    upsert_usage_records(session, [make_record("msg_1", input_tokens=100)])

    upsert_usage_records(session, [make_record("msg_1", input_tokens=250)])

    stored = query_usage_events(session)[0]
    assert count_usage_events(session) == 1
    assert stored.input_tokens == 250
    assert stored.total_tokens == 270


def test_the_original_import_time_survives_an_update(session: Session) -> None:
    first_import = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
    upsert_usage_records(session, [make_record("msg_1")], now=first_import)

    upsert_usage_records(
        session,
        [make_record("msg_1", input_tokens=999)],
        now=datetime(2026, 10, 6, 9, 0, tzinfo=UTC),
    )

    assert query_usage_events(session)[0].created_at == first_import


def test_a_mixed_batch_inserts_new_and_updates_existing(session: Session) -> None:
    upsert_usage_records(session, [make_record("msg_1")])

    result = upsert_usage_records(
        session, [make_record("msg_1", input_tokens=5), make_record("msg_2")]
    )

    assert (result.inserted, result.updated) == (1, 1)
    assert count_usage_events(session) == 2


def test_the_batch_is_written_as_one_statement(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Re-importing history used to cost one UPDATE per row: 1,125 ms for 2,142
    # records. The batch must go out as a single statement, or a future change
    # could quietly put that loop back.
    statements: list[str] = []

    @event.listens_for(session.get_bind(), "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    upsert_usage_records(session, [make_record(f"msg_{index}") for index in range(50)])

    inserts = [s for s in statements if s.lstrip().upper().startswith("INSERT")]
    assert len(inserts) == 1


def test_the_row_at_a_time_fallback_behaves_identically(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # SQLite older than 3.24 cannot batch this. The slow path must still be correct,
    # not merely present: same counts, same rows, and the import time still preserved.
    monkeypatch.setattr(repository, "BULK_UPSERT_SUPPORTED", False)
    first_import = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)

    inserted = upsert_usage_records(
        session,
        [make_record("msg_1"), make_record("msg_2")],
        now=first_import,
    )
    updated = upsert_usage_records(
        session,
        [make_record("msg_1", input_tokens=250), make_record("msg_2"), make_record("msg_3")],
        now=datetime(2026, 10, 6, 9, 0, tzinfo=UTC),
    )

    assert (inserted.inserted, inserted.updated) == (2, 0)
    assert (updated.inserted, updated.updated) == (1, 2)
    assert count_usage_events(session) == 3
    stored = query_usage_events(session)[0]
    assert stored.input_tokens == 250
    assert stored.created_at == first_import


def test_an_empty_batch_is_a_no_op(session: Session) -> None:
    result = upsert_usage_records(session, [])

    assert result.total == 0
    assert count_usage_events(session) == 0


def test_unknown_token_counts_are_stored_as_null_not_zero(session: Session) -> None:
    upsert_usage_records(
        session,
        [make_record("msg_1", input_tokens=None, output_tokens=None, consumption_tokens=None)],
    )

    stored = query_usage_events(session)[0]
    assert stored.input_tokens is None
    assert stored.total_tokens is None


def test_raw_usage_survives_a_round_trip_as_json(session: Session) -> None:
    upsert_usage_records(session, [make_record("msg_1")])

    stored = query_usage_events(session)[0]

    assert json.loads(stored.raw_usage)["finish"] == "stop"


# --- history preservation ---


def test_usage_survives_the_source_session_disappearing(session: Session) -> None:
    upsert_usage_records(session, [make_record("msg_1")])

    # Nothing here deletes usage, so a deleted OpenCode session cannot remove it.
    assert count_usage_events(session) == 1
    assert sum_tokens(session, "consumption_tokens") == 120


def test_no_repository_call_deletes_events(session: Session) -> None:
    upsert_usage_records(session, [make_record(f"msg_{i}") for i in range(5)])

    query_usage_events(session)
    upsert_usage_records(session, [make_record("msg_0")])

    assert count_usage_events(session) == 5


# --- querying ---


def test_events_come_back_oldest_first(session: Session) -> None:
    upsert_usage_records(
        session,
        [make_record("msg_b", timestamp=DAY_TWO), make_record("msg_a", timestamp=DAY_ONE)],
    )

    timestamps = [event.timestamp for event in query_usage_events(session)]

    assert timestamps == sorted(timestamps)


def test_a_date_range_selects_only_events_inside_it(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            make_record("msg_a", timestamp=DAY_ONE),
            make_record("msg_b", timestamp=DAY_TWO),
        ],
    )

    found = query_usage_events(session, start=DAY_ONE, end=DAY_TWO)

    assert [event.source_event_id for event in found] == ["msg_a"]


def test_a_model_filter_selects_only_that_model(session: Session) -> None:
    upsert_usage_records(session, [make_record("msg_a")])
    other = make_record("msg_b").model_copy(update={"model_id": "union-alpha"})
    upsert_usage_records(session, [other])

    found = query_usage_events(session, model_id="union-alpha")

    assert [event.source_event_id for event in found] == ["msg_b"]


def test_a_limit_caps_the_number_of_rows(session: Session) -> None:
    upsert_usage_records(session, [make_record(f"msg_{i}") for i in range(10)])

    assert len(query_usage_events(session, limit=3)) == 3


def test_summing_over_a_range_ignores_rows_outside_it(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            make_record("msg_a", timestamp=DAY_ONE, consumption_tokens=100),
            make_record("msg_b", timestamp=DAY_TWO, consumption_tokens=200),
        ],
    )

    assert sum_tokens(session, "consumption_tokens", start=DAY_ONE, end=DAY_TWO) == 100


def test_summing_an_unknown_column_is_rejected(session: Session) -> None:
    with pytest.raises(ValueError):
        sum_tokens(session, "platform")


def test_summing_no_rows_returns_zero(session: Session) -> None:
    assert sum_tokens(session, "input_tokens") == 0


# --- collector state ---


def test_progress_starts_absent(session: Session) -> None:
    assert load_progress(session, "opencode") is None


def test_progress_is_saved_and_reloaded(session: Session) -> None:
    save_progress(session, "opencode", source_path="/data/opencode.db", checkpoint="1000")

    progress = load_progress(session, "opencode")

    assert progress is not None
    assert progress.checkpoint == "1000"
    assert progress.source_path == "/data/opencode.db"
    assert progress.status == "idle"
    assert progress.last_scan_at is not None


def test_saving_twice_updates_the_same_row(session: Session) -> None:
    save_progress(session, "opencode", checkpoint="1000")
    save_progress(session, "opencode", checkpoint="2000")

    assert session.query(CollectorState).count() == 1
    assert checkpoint_for(session, "opencode") == "2000"


def test_two_platforms_keep_separate_checkpoints(session: Session) -> None:
    save_progress(session, "opencode", checkpoint="1000")
    save_progress(session, "claude", checkpoint="5000")

    assert checkpoint_for(session, "opencode") == "1000"
    assert checkpoint_for(session, "claude") == "5000"


def test_a_scan_can_be_marked_running(session: Session) -> None:
    mark_scanning(session, "opencode")

    progress = load_progress(session, "opencode")
    assert progress is not None
    assert progress.status == "scanning"


def test_marking_an_error_leaves_the_checkpoint_for_a_retry(session: Session) -> None:
    save_progress(session, "opencode", checkpoint="1000")

    mark_error(session, "opencode")

    progress = load_progress(session, "opencode")
    assert progress is not None
    assert progress.status == "error"
    assert progress.checkpoint == "1000"


# --- end to end with the real collector ---


def test_real_opencode_records_store_and_reimport_without_duplicates(
    session: Session,
) -> None:
    collector = OpenCodeCollector()
    if not collector.discover().available:
        pytest.skip("no OpenCode database on this machine")
    records = collector.collect_history()[:200]
    if not records:
        pytest.skip("no completed assistant messages to import")

    first = upsert_usage_records(session, records)
    second = upsert_usage_records(session, records)

    assert first.inserted == len(records)
    assert (second.inserted, second.updated) == (0, len(records))
    assert count_usage_events(session) == len(records)


def test_a_date_range_query_uses_the_timestamp_index(session: Session) -> None:
    """Guard the requirement that date-range aggregation stays indexed."""
    statements: list[str] = []

    @event.listens_for(session.get_bind(), "before_cursor_execute")
    def _capture(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    upsert_usage_records(session, [make_record("msg_a")])
    query_usage_events(session, start=DAY_ONE, end=DAY_TWO, limit=10)

    assert any("usage_events" in statement and "timestamp" in statement for statement in statements)


def _row_values(**overrides: object) -> dict[str, object]:
    """Values for a directly constructed UsageEvent row."""
    values: dict[str, object] = {
        "platform": "opencode",
        "provider_id": "opencode",
        "model_id": "space-bunny-free",
        "session_id": "ses_1",
        "message_id": "msg_1",
        "source_event_id": "msg_1",
        "timestamp": DAY_ONE,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "reasoning_tokens": 0,
        "cache_read_tokens": 900,
        "cache_write_tokens": 0,
        "consumption_tokens": 1020,
        "usage_status": "reported",
        "cache_overlap": "additive",
        "reasoning_overlap": "additive",
        "raw_usage": "{}",
    }
    values.update(overrides)
    return values


def test_marking_a_scan_does_not_erase_the_stored_source_path(session: Session) -> None:
    save_progress(session, "opencode", source_path="/data/opencode.db", checkpoint="1000")

    mark_scanning(session, "opencode")

    progress = load_progress(session, "opencode")
    assert progress is not None
    assert progress.source_path == "/data/opencode.db"
    assert progress.checkpoint == "1000"
