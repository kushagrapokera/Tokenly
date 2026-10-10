"""Learning tests: pin OpenCode's real storage shapes so an upgrade fails fast.

Clean Code ch08 (Boundaries): OpenCode's SQLite schema and its `message.data` JSON are a
third-party boundary. These tests assert the contract the collector was written against,
documented in `docs/opencode_storage_analysis.md` and verified against OpenCode 1.18.35.

They run against the developer's real OpenCode database when one exists, and skip when it
does not, so the suite stays green on a machine with no OpenCode installed. When OpenCode
upgrades and changes a shape, these fail here instead of silently skewing totals.
"""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from collectors.opencode import OpenCodeCollector
from collectors.opencode.locator import resolve_database_path
from collectors.opencode.reader import (
    count_assistant_messages,
    iter_assistant_messages,
    list_sessions,
    open_snapshot,
)
from collectors.opencode.snapshot import snapshot_database
from config.settings import get_settings

ASSISTANT = "assistant"


@pytest.fixture(scope="module")
def live_database_path() -> Iterator[Path]:
    """The real OpenCode database, or skip when this machine has none."""
    database_path = resolve_database_path(get_settings())
    if not database_path.is_file():
        pytest.skip(f"no OpenCode database at {database_path}")
    yield database_path


@pytest.fixture(scope="module")
def live_connection(live_database_path: Path) -> Iterator[sqlite3.Connection]:
    """A read-only connection to a snapshot of the real database."""
    with snapshot_database(live_database_path) as snapshot_path:
        connection = open_snapshot(snapshot_path)
        try:
            yield connection
        finally:
            connection.close()


def test_the_database_is_sqlite_with_the_tables_the_reader_expects(
    live_database_path: Path,
) -> None:
    assert live_database_path.suffix == ".db"
    with snapshot_database(live_database_path) as snapshot_path:
        connection = open_snapshot(snapshot_path)  # raises if a table is missing
        connection.close()


def test_the_message_table_has_the_columns_the_reader_selects(
    live_connection: sqlite3.Connection,
) -> None:
    columns = {row[1] for row in live_connection.execute("PRAGMA table_info(message)")}

    assert {"id", "session_id", "time_created", "data"} <= columns


def test_the_session_table_has_the_columns_the_reader_selects(
    live_connection: sqlite3.Connection,
) -> None:
    columns = {row[1] for row in live_connection.execute("PRAGMA table_info(session)")}

    assert {"id", "time_created"} <= columns


def test_every_message_payload_is_a_json_object(live_connection: sqlite3.Connection) -> None:
    invalid = live_connection.execute(
        "SELECT COUNT(*) FROM message WHERE json_valid(data) = 0"
    ).fetchone()[0]

    assert invalid == 0


def test_roles_are_only_user_or_assistant(live_connection: sqlite3.Connection) -> None:
    roles = {
        row[0]
        for row in live_connection.execute(
            "SELECT DISTINCT json_extract(data, '$.role') FROM message"
        )
    }

    assert roles <= {"user", ASSISTANT}


def test_message_ids_are_unique_so_they_can_key_records(
    live_connection: sqlite3.Connection,
) -> None:
    total, distinct = live_connection.execute(
        "SELECT COUNT(*), COUNT(DISTINCT id) FROM message"
    ).fetchone()

    assert total == distinct


def test_message_ids_are_prefixed_so_they_cannot_collide_across_sessions(
    live_connection: sqlite3.Connection,
) -> None:
    odd = live_connection.execute(
        "SELECT COUNT(*) FROM message WHERE id NOT LIKE 'msg\\_%' ESCAPE '\\'"
    ).fetchone()[0]

    assert odd == 0


def test_timestamps_are_integer_milliseconds_in_a_plausible_range(
    live_connection: sqlite3.Connection,
) -> None:
    rows = live_connection.execute("SELECT time_created FROM message").fetchall()

    assert rows
    for (value,) in rows:
        assert isinstance(value, int)
        assert 1_000_000_000_000 < value < 4_000_000_000_000


def test_the_json_created_field_agrees_with_the_time_created_column(
    live_connection: sqlite3.Connection,
) -> None:
    mismatches = live_connection.execute(
        "SELECT COUNT(*) FROM message "
        "WHERE json_extract(data, '$.time.created') IS NOT NULL "
        "AND json_extract(data, '$.time.created') != time_created"
    ).fetchone()[0]

    assert mismatches == 0


def test_assistant_messages_carry_provider_and_model_identity(
    live_connection: sqlite3.Connection,
) -> None:
    missing = live_connection.execute(
        f"SELECT COUNT(*) FROM message WHERE json_extract(data, '$.role') = '{ASSISTANT}' "
        "AND (json_extract(data, '$.providerID') IS NULL "
        "OR json_extract(data, '$.modelID') IS NULL)"
    ).fetchone()[0]

    assert missing == 0


def test_assistant_messages_carry_a_created_timestamp(
    live_connection: sqlite3.Connection,
) -> None:
    missing = live_connection.execute(
        f"SELECT COUNT(*) FROM message WHERE json_extract(data, '$.role') = '{ASSISTANT}' "
        "AND json_extract(data, '$.time.created') IS NULL"
    ).fetchone()[0]

    assert missing == 0


def test_the_tokens_object_keeps_the_documented_shape(
    live_connection: sqlite3.Connection,
) -> None:
    """`input`, `output`, `reasoning` and `cache` are what the analysis documented."""
    shapes = {
        tuple(sorted(row[0].split(",")))
        for row in live_connection.execute(
            f"SELECT DISTINCT "
            f"COALESCE((SELECT group_concat(key) FROM json_each(message.data, '$.tokens')), '') "
            f"FROM message WHERE json_extract(data, '$.role') = '{ASSISTANT}' "
            "AND json_type(data, '$.tokens') = 'object'"
        )
    }

    assert shapes <= {
        ("cache", "input", "output", "reasoning"),
        ("cache", "input", "output", "reasoning", "total"),
    }


def test_the_reported_total_also_counts_reasoning_and_cache(
    live_connection: sqlite3.Connection,
) -> None:
    """The reason the collector never trusts tokens.total: it is not input + output."""
    totals = live_connection.execute(
        f"SELECT COUNT(*) FROM message WHERE json_extract(data, '$.role') = '{ASSISTANT}' "
        "AND json_extract(data, '$.tokens.total') IS NOT NULL "
        "AND json_extract(data, '$.tokens.total') != "
        "json_extract(data, '$.tokens.input') + json_extract(data, '$.tokens.output')"
    ).fetchone()[0]

    assert totals > 0, "expected at least some totals to include reasoning/cache"


def test_some_messages_are_missing_a_total_so_it_cannot_be_required(
    live_connection: sqlite3.Connection,
) -> None:
    missing = live_connection.execute(
        f"SELECT COUNT(*) FROM message WHERE json_extract(data, '$.role') = '{ASSISTANT}' "
        "AND json_extract(data, '$.tokens') IS NOT NULL "
        "AND json_extract(data, '$.tokens.total') IS NULL"
    ).fetchone()[0]

    assert missing > 0


def test_an_in_flight_message_exists_so_the_deferral_rule_is_real(
    live_connection: sqlite3.Connection,
) -> None:
    """Only meaningful while a generation is running; skipped when none is."""
    in_flight = live_connection.execute(
        f"SELECT COUNT(*) FROM message WHERE json_extract(data, '$.role') = '{ASSISTANT}' "
        "AND json_extract(data, '$.time.completed') IS NULL"
    ).fetchone()[0]

    if in_flight == 0:
        pytest.skip("no generation currently in flight")


def test_session_rollups_equal_the_sum_of_their_messages(
    live_connection: sqlite3.Connection,
) -> None:
    """Cross-check from the analysis: session tokens are a rollup, never a second source."""
    mismatched = []
    for session in list_sessions(live_connection):
        rows = live_connection.execute(
            "SELECT data FROM message WHERE session_id = ? AND json_extract(data, '$.role') = ?",
            (session.session_id, ASSISTANT),
        ).fetchall()
        input_total = output_total = 0
        for (payload,) in rows:
            tokens = json.loads(payload).get("tokens") or {}
            input_total += tokens.get("input", 0)
            output_total += tokens.get("output", 0)
        stored = live_connection.execute(
            "SELECT tokens_input, tokens_output FROM session WHERE id = ?",
            (session.session_id,),
        ).fetchone()
        if stored is not None and tuple(stored) != (input_total, output_total):
            mismatched.append(session.session_id)

    assert mismatched == []


def test_the_collector_reports_the_database_as_available(live_database_path: Path) -> None:
    result = OpenCodeCollector().discover()

    assert result.available is True
    assert result.storage_format == "sqlite"


def test_collecting_from_the_real_database_produces_usable_records() -> None:
    records = OpenCodeCollector().collect_history()

    assert records
    assert all(record.platform == "opencode" for record in records)
    assert all(record.provider_id and record.model_id for record in records)
    assert all(record.timestamp.tzinfo is not None for record in records)


def test_record_ids_are_unique_when_collected_from_the_real_database() -> None:
    records = OpenCodeCollector().collect_history()

    ids = [record.source_event_id for record in records]
    assert len(ids) == len(set(ids))


def test_every_total_equals_its_input_plus_output_on_real_data() -> None:
    records = OpenCodeCollector().collect_history()

    complete = [record for record in records if record.total_tokens is not None]
    assert complete
    for record in complete:
        assert record.input_tokens is not None
        assert record.output_tokens is not None
        assert record.total_tokens == record.input_tokens + record.output_tokens


def test_unavailable_usage_is_null_rather_than_zero_on_real_data() -> None:
    records = OpenCodeCollector().collect_history()

    for record in records:
        if record.usage_status == "unavailable":
            assert record.input_tokens is None
            assert record.output_tokens is None
            assert record.total_tokens is None
        else:
            assert record.usage_status == "reported"


def test_the_reader_and_the_raw_count_agree_on_real_data(
    live_connection: sqlite3.Connection,
) -> None:
    rows = list(iter_assistant_messages(live_connection))

    assert len(rows) == count_assistant_messages(live_connection)
