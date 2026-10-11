"""Learning tests: pin Claude Code's real storage shapes so an upgrade fails fast.

Clean Code ch08 (Boundaries): Claude Code's JSONL transcript layout is a
third-party boundary. These tests assert the contract the collector was
written against, documented in `docs/claude_storage_analysis.md` and verified
against Claude Code 2.1.278/2.1.282 on 2026-10-12.

They run against this machine's real Claude store when one exists, and skip
when it does not, so the suite stays green elsewhere. When Claude Code
upgrades and changes a shape, these fail here instead of silently skewing
totals.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from collectors.claude import ClaudeCodeCollector
from collectors.claude.collector import STORAGE_FORMAT
from collectors.claude.locator import platform_default_data_directory, resolve_projects_directory
from config.settings import get_settings


@pytest.fixture(scope="module")
def live_projects_dir() -> Iterator[Path]:
    """The real Claude projects directory, or skip when this machine has none."""
    projects_dir = resolve_projects_directory(get_settings())
    if not projects_dir.is_dir():
        pytest.skip(f"no Claude Code projects directory at {projects_dir}")
    yield projects_dir


def test_transcripts_are_jsonl_named_after_their_session(live_projects_dir: Path) -> None:
    transcripts = sorted(live_projects_dir.glob("*/*.jsonl"))
    assert transcripts
    assert all(path.stem for path in transcripts)


def test_assistant_lines_carry_the_keys_the_extractor_maps(
    live_projects_dir: Path,
) -> None:
    import json

    checked = 0
    for transcript in sorted(live_projects_dir.glob("*/*.jsonl")):
        for line in transcript.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("type") != "assistant":
                continue
            message = payload.get("message") or {}
            assert isinstance(message.get("usage"), dict)
            assert {"id", "role", "model", "usage"} <= set(message)
            assert {"input_tokens", "output_tokens"} <= set(message["usage"])
            assert {"type", "timestamp", "sessionId"} <= set(payload)
            checked += 1
            if checked >= 5:
                return

    assert checked > 0


def test_usage_carry_the_optional_fields_the_extractor_maps(
    live_projects_dir: Path,
) -> None:
    import json

    for transcript in sorted(live_projects_dir.glob("*/*.jsonl")):
        for line in transcript.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("type") != "assistant":
                continue
            usage = payload["message"]["usage"]
            for key in (
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "output_tokens_details",
            ):
                assert key in usage, key
            return
    pytest.fail("no assistant line found to check")


def test_repeated_message_ids_share_identical_usage(live_projects_dir: Path) -> None:
    """The dedup rule's load-bearing premise: lines of one id carry the same usage."""
    import json
    from collections import defaultdict

    usage_by_id: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for transcript in sorted(live_projects_dir.glob("*/*.jsonl")):
        for line in transcript.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("type") != "assistant":
                continue
            message = payload["message"]
            usage = message["usage"]
            usage_by_id[message["id"]].add(
                (usage["input_tokens"], usage["output_tokens"])
            )

    assert usage_by_id, "store holds no assistant lines"
    for message_id, variants in usage_by_id.items():
        assert len(variants) == 1, f"message {message_id} usage varies between its lines"


def test_collecting_from_the_real_store_produces_usable_records(
    live_projects_dir: Path,
) -> None:
    records = ClaudeCodeCollector(get_settings()).collect_history()

    assert records
    assert all(record.platform == "claude_code" for record in records)
    assert all(record.timestamp.tzinfo is not None for record in records)
    assert all(":" in record.source_event_id for record in records)


def test_record_ids_are_unique_after_collapse(live_projects_dir: Path) -> None:
    """The 165-lines-to-58-requests store must yield one record per request."""
    records = ClaudeCodeCollector(get_settings()).collect_history()

    ids = [record.source_event_id for record in records]
    assert len(ids) == len(set(ids))


def test_record_count_matches_distinct_message_ids(live_projects_dir: Path) -> None:
    """Collapse must count requests, not lines: the 2.84x repetition is the trap."""
    import json

    distinct_ids: set[str] = set()
    live_line_count = 0
    for transcript in sorted(live_projects_dir.glob("*/*.jsonl")):
        for line in transcript.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("type") != "assistant":
                continue
            live_line_count += 1
            distinct_ids.add(f"{payload['sessionId']}:{payload['message']['id']}")

    records = ClaudeCodeCollector(get_settings()).collect_history()

    assert len(records) == len(distinct_ids)
    # The repetition must exist for this test to mean anything:
    assert live_line_count > len(distinct_ids)


def test_every_total_equals_its_input_plus_output_on_real_data(
    live_projects_dir: Path,
) -> None:
    records = ClaudeCodeCollector(get_settings()).collect_history()

    complete = [record for record in records if record.total_tokens is not None]
    assert complete
    for record in complete:
        assert record.input_tokens is not None
        assert record.output_tokens is not None
        assert record.total_tokens == record.input_tokens + record.output_tokens


def test_a_gateway_prefix_sets_the_provider_and_a_bare_name_stays_unknown(
    live_projects_dir: Path,
) -> None:
    records = ClaudeCodeCollector(get_settings()).collect_history()

    for record in records:
        if record.model_id.startswith(("openrouter/", "bedrock/", "deepseek/")):
            assert record.provider_id != "unknown"
        else:
            assert record.provider_id == "unknown"


def test_the_collector_reports_the_store_as_available(live_projects_dir: Path) -> None:
    result = ClaudeCodeCollector(get_settings()).discover()

    assert result.available is True
    assert result.storage_format == STORAGE_FORMAT


def test_the_platform_default_is_the_home_directory() -> None:
    # Resolved at runtime; the fallback must be the documented `~/.claude`.
    default = platform_default_data_directory()
    assert default.name == ".claude"
