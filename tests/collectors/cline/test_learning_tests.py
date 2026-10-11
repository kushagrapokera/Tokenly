"""Learning tests: pin Cline CLI's real storage shapes so an upgrade fails fast.

Clean Code ch08 (Boundaries): Cline's session index schema and its
`.messages.json` shape are a third-party boundary. These tests assert the
contract the collector was written against, documented in
`docs/cline_storage_analysis.md` and verified against Cline CLI 3.0.70.

They run against the developer's real Cline store when one exists, and skip
when it does not, so the suite stays green on a machine with no Cline
installed. When Cline upgrades and changes a shape, these fail here instead
of silently skewing totals.
"""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from collectors.cline import ClineCollector
from collectors.cline.collector import STORAGE_FORMAT
from collectors.cline.locator import resolve_data_directory, resolve_sessions_directory
from collectors.cline.reader import session_ids_in_directory
from collectors.cline.snapshot import snapshot_database
from config.settings import get_settings


@pytest.fixture(scope="module")
def live_data_dir() -> Iterator[Path]:
    """The real Cline data directory, or skip when this machine has none."""
    data_dir = resolve_data_directory(get_settings())
    if not (data_dir / "sessions").is_dir():
        pytest.skip(f"no Cline sessions directory at {data_dir / 'sessions'}")
    yield data_dir


def test_session_index_holds_the_columns_the_reader_selects(
    live_data_dir: Path,
) -> None:
    index_path = live_data_dir / "db" / "sessions.db"
    if not index_path.is_file():
        pytest.skip(f"no Cline session index at {index_path}")
    with snapshot_database(index_path) as snapshot_path:
        with sqlite3.connect(f"file:{snapshot_path}?mode=ro", uri=True) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}

    assert {"session_id", "messages_path"} <= columns


def test_session_files_carry_the_message_shape_the_reader_expects(
    live_data_dir: Path,
) -> None:
    checked = 0
    for session_id in session_ids_in_directory(live_data_dir / "sessions")[:3]:
        messages_path = live_data_dir / "sessions" / session_id / f"{session_id}.messages.json"
        if not messages_path.is_file():
            continue
        payload = json.loads(messages_path.read_text(encoding="utf-8"))
        assert isinstance(payload.get("messages"), list)
        for message in payload["messages"]:
            assert {"id", "role", "ts"} <= set(message)
            if message["role"] == "assistant":
                assert "modelInfo" in message
        checked += 1

    assert checked > 0


def test_assistant_metrics_carry_the_four_fields_the_extractor_maps(
    live_data_dir: Path,
) -> None:
    seen = 0
    for session_id in session_ids_in_directory(live_data_dir / "sessions"):
        messages_path = live_data_dir / "sessions" / session_id / f"{session_id}.messages.json"
        if not messages_path.is_file():
            continue
        payload = json.loads(messages_path.read_text(encoding="utf-8"))
        for message in payload.get("messages", []):
            metrics = message.get("metrics")
            if message.get("role") == "assistant" and isinstance(metrics, dict):
                assert {
                    "inputTokens",
                    "outputTokens",
                    "cacheReadTokens",
                    "cacheWriteTokens",
                } <= set(metrics)
                seen += 1
                if seen >= 5:
                    return

    assert seen > 0


def test_every_total_equals_its_input_plus_output_on_real_data(live_data_dir: Path) -> None:
    records = ClineCollector().collect_history()

    complete = [record for record in records if record.total_tokens is not None]
    assert complete
    for record in complete:
        assert record.input_tokens is not None
        assert record.output_tokens is not None
        assert record.total_tokens == record.input_tokens + record.output_tokens


def test_unavailable_usage_is_null_rather_than_zero_on_real_data(live_data_dir: Path) -> None:
    records = ClineCollector().collect_history()

    for record in records:
        if record.usage_status == "unavailable":
            assert record.input_tokens is None
            assert record.output_tokens is None
            assert record.total_tokens is None
        else:
            assert record.usage_status == "reported"


def test_the_collector_reports_the_store_as_available(live_data_dir: Path) -> None:
    assert resolve_sessions_directory(get_settings()).is_dir()

    result = ClineCollector().discover()

    assert result.available is True
    assert result.storage_format == STORAGE_FORMAT


def test_collecting_from_the_real_store_produces_usable_records(live_data_dir: Path) -> None:
    records = ClineCollector().collect_history()

    assert records
    assert all(record.platform == "cline" for record in records)
    assert all(record.provider_id and record.model_id for record in records)
    assert all(record.timestamp.tzinfo is not None for record in records)


def test_record_ids_are_unique_when_collected_from_the_real_store(live_data_dir: Path) -> None:
    records = ClineCollector().collect_history()

    ids = [record.source_event_id for record in records]
    assert len(ids) == len(set(ids))
