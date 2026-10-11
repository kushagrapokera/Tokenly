"""Learning tests: pin Codex CLI's real storage shapes so an upgrade fails fast.

Clean Code ch08 (Boundaries): Codex CLI's rollout JSONL layout is a third-party
boundary. These tests assert the contract the collector was written against,
documented in `docs/codex_storage_analysis.md` and verified against Codex CLI
0.155.1 on 2026-10-12.

They run against this machine's real Codex store when one exists (via
`CODEX_HOME`, falling back to `~/.codex`) and skip when it does not, so the suite
stays green elsewhere. When Codex CLI upgrades and changes a shape, these fail
here instead of silently skewing totals.

Run them against a custom home with: `CODEX_HOME=/path/to/codex pytest ...`
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from collectors.codex import CodexCollector
from collectors.codex.collector import STORAGE_FORMAT
from collectors.codex.locator import platform_default_home_directory, resolve_sessions_directory
from config.settings import get_settings

USAGE_LINE_TYPE = "token_usage_record"
SESSION_META_TYPE = "session_meta"
TURN_CONTEXT_TYPE = "turn_context"

# Every top-level line type the live store has been observed to write.
EXPECTED_LINE_TYPES = {
    "session_meta",
    "event_msg",
    "response_item",
    "world_state",
    "turn_context",
    "token_usage_record",
}

# The identity fields every `token_usage_record` payload carries.
RECORD_KEYSET = {
    "thread_id",
    "turn_id",
    "session_id",
    "root_turn_id",
    "response_id",
    "usage",
    "turn_token_usage",
    "thread_token_usage",
}

# The six fields of Codex's usage object.
USAGE_FIELDS = {
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
}


@pytest.fixture(scope="module")
def live_sessions_dir() -> Iterator[Path]:
    """The real Codex sessions directory, or skip when this machine has none."""
    sessions_dir = resolve_sessions_directory(get_settings())
    if not sessions_dir.is_dir():
        pytest.skip(f"no Codex sessions directory at {sessions_dir}")
    yield sessions_dir


def _rollout_files(sessions_dir: Path) -> list[Path]:
    return sorted(sessions_dir.rglob("rollout-*.jsonl"))


def _envelopes(sessions_dir: Path) -> Iterator[dict]:
    for path in _rollout_files(sessions_dir):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            yield json.loads(line)


def test_rollout_files_live_under_date_folders(live_sessions_dir: Path) -> None:
    files = _rollout_files(live_sessions_dir)
    assert files
    for path in files:
        relative = path.relative_to(live_sessions_dir).parts
        # sessions/YYYY/MM/DD/rollout-*.jsonl -> four parts under the sessions dir.
        assert len(relative) == 4, relative
        year, month, day, name = relative
        assert year.isdigit() and month.isdigit() and day.isdigit()
        assert name.startswith("rollout-") and name.endswith(".jsonl")


def test_every_line_is_an_envelope_with_the_expected_keys(live_sessions_dir: Path) -> None:
    checked = 0
    for envelope in _envelopes(live_sessions_dir):
        assert {"timestamp", "ordinal", "type", "payload"} <= set(envelope), envelope
        assert isinstance(envelope["payload"], dict)
        checked += 1
        if checked >= 20:
            return
    assert checked > 0


def test_the_six_documented_line_types_are_the_only_ones(live_sessions_dir: Path) -> None:
    observed = {envelope["type"] for envelope in _envelopes(live_sessions_dir)}
    # Every line Codex writes is one of the six we documented; a new one means the
    # storage analysis (and possibly the reader) needs revisiting.
    assert observed <= EXPECTED_LINE_TYPES
    # The types the collector depends on must actually be present.
    assert {SESSION_META_TYPE, TURN_CONTEXT_TYPE, USAGE_LINE_TYPE} <= observed


def test_token_usage_records_carry_the_full_identity_keyset(
    live_sessions_dir: Path,
) -> None:
    checked = 0
    for envelope in _envelopes(live_sessions_dir):
        if envelope["type"] != USAGE_LINE_TYPE:
            continue
        assert RECORD_KEYSET <= set(envelope["payload"]), envelope["payload"].keys()
        checked += 1
        if checked >= 10:
            return
    assert checked > 0, "store holds no token_usage_record lines"


def test_the_usage_object_has_exactly_the_six_fields(live_sessions_dir: Path) -> None:
    checked = 0
    for envelope in _envelopes(live_sessions_dir):
        if envelope["type"] != USAGE_LINE_TYPE:
            continue
        usage = envelope["payload"]["usage"]
        assert set(usage) == USAGE_FIELDS, set(usage)
        checked += 1
        if checked >= 10:
            return
    assert checked > 0


def test_total_tokens_always_equals_input_plus_output(live_sessions_dir: Path) -> None:
    """Codex's own `total` never adds the cached/reasoning subsets — the join must match."""
    checked = 0
    for envelope in _envelopes(live_sessions_dir):
        if envelope["type"] != USAGE_LINE_TYPE:
            continue
        usage = envelope["payload"]["usage"]
        assert usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]
        assert usage["cached_input_tokens"] <= usage["input_tokens"]
        assert usage["reasoning_output_tokens"] <= usage["output_tokens"]
        checked += 1
    assert checked > 0


def test_per_call_usage_reconciles_to_the_session_rollup(live_sessions_dir: Path) -> None:
    """`sum(usage.total)` must equal the final `thread_token_usage.total` per session.

    This is the load-bearing invariant: it proves the per-call scope we ingest is
    the complete truth and the rollups are exact sums of it, so reading only the
    per-call scope loses nothing.
    """
    reconciled = 0
    for path in _rollout_files(live_sessions_dir):
        per_call_total = 0
        final_thread_total = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            envelope = json.loads(line)
            if envelope["type"] != USAGE_LINE_TYPE:
                continue
            per_call_total += envelope["payload"]["usage"]["total_tokens"]
            thread_usage = envelope["payload"].get("thread_token_usage") or {}
            if "total_tokens" in thread_usage:
                final_thread_total = thread_usage["total_tokens"]
        if final_thread_total is None:
            continue
        assert per_call_total == final_thread_total, path
        reconciled += 1
    assert reconciled > 0


def test_provider_and_model_metadata_are_present_on_real_lines(
    live_sessions_dir: Path,
) -> None:
    providers: set[str] = set()
    models: set[str] = set()
    for envelope in _envelopes(live_sessions_dir):
        if envelope["type"] == SESSION_META_TYPE:
            providers.add(envelope["payload"].get("model_provider"))
        elif envelope["type"] == TURN_CONTEXT_TYPE:
            models.add(envelope["payload"].get("model"))
    # The join must have real values to read; `None` would mean the keys moved.
    assert providers - {None}
    assert models - {None}


def test_the_collector_reports_the_store_as_available(live_sessions_dir: Path) -> None:
    result = CodexCollector(get_settings()).discover()

    assert result.available is True
    assert result.storage_format == STORAGE_FORMAT


def test_collecting_from_the_real_store_produces_usable_records(
    live_sessions_dir: Path,
) -> None:
    records = CodexCollector(get_settings()).collect_history()

    assert records
    assert all(record.platform == "codex" for record in records)
    assert all(record.timestamp.tzinfo is not None for record in records)
    assert all(":" in record.source_event_id for record in records)


def test_record_ids_are_unique_after_collapse(live_sessions_dir: Path) -> None:
    """One record per `{session}:{response}` — the rollups and echoes add none."""
    records = CodexCollector(get_settings()).collect_history()

    ids = [record.source_event_id for record in records]
    assert len(ids) == len(set(ids))


def test_every_real_total_equals_input_plus_output(live_sessions_dir: Path) -> None:
    records = CodexCollector(get_settings()).collect_history()

    complete = [record for record in records if record.total_tokens is not None]
    assert complete
    for record in complete:
        assert record.total_tokens == (record.input_tokens or 0) + (record.output_tokens or 0)


def test_real_records_carry_the_joined_provider_and_model(
    live_sessions_dir: Path,
) -> None:
    records = CodexCollector(get_settings()).collect_history()

    # session_meta says `deepseek`; turn_context says `deepseek-flash`.
    assert all(record.provider_id == "deepseek" for record in records)
    assert all(record.model_id == "deepseek-flash" for record in records)


def test_the_platform_default_is_the_home_directory() -> None:
    # Resolved at runtime; the fallback must be the documented `~/.codex`.
    default = platform_default_home_directory()
    assert default.name == ".codex"
