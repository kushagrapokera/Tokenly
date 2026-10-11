"""Unit tests for the Codex extractor.

These drive the documented field map (`docs/codex_storage_analysis.md` §4, §9)
through stand-in usage events built with the fixture's real shape, asserting the
normalized output the shared pipeline stores.
"""

from datetime import datetime, timezone

from collectors.codex.extractor import (
    PLATFORM,
    UNKNOWN_VALUE,
    extract_usage_record,
    namespaced_event_id,
)
from collectors.codex.reader import CodexUsageEvent
from tests.collectors.codex.conftest import (
    MODEL_DEFAULT,
    PROVIDER_DEFAULT,
    RESPONSE_DEFAULT_ID,
    SES_DEFAULT_ID,
    TURN_DEFAULT_ID,
)

TIMESTAMP = "2026-09-22T12:53:47.767Z"


def usage_event(
    *,
    session_id: str = SES_DEFAULT_ID,
    response_id: str = RESPONSE_DEFAULT_ID,
    turn_id: str = TURN_DEFAULT_ID,
    model_id: str | None = MODEL_DEFAULT,
    provider_id: str | None = PROVIDER_DEFAULT,
    timestamp: datetime | None = datetime(2026, 9, 22, 12, 53, 47, 767_000, tzinfo=timezone.utc),
    usage: dict | None = None,
) -> CodexUsageEvent:
    """Build one standalone usage event through the fixture's real six-field shape."""
    if usage is None:
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 40,
            "cache_write_input_tokens": 0,
            "output_tokens": 20,
            "reasoning_output_tokens": 5,
            "total_tokens": 120,
        }
    return CodexUsageEvent(
        session_id=session_id,
        turn_id=turn_id,
        response_id=response_id,
        timestamp=timestamp,
        model_id=model_id,
        provider_id=provider_id,
        usage=usage,
        raw_payload={"response_id": response_id},
        cli_version="0.155.1",
    )


# --- platform and identity ---


def test_platform_is_codex() -> None:
    assert PLATFORM == "codex"


def test_event_id_is_namespaced_by_session_and_response() -> None:
    assert namespaced_event_id("ses_a", "resp_1") == "ses_a:resp_1"


def test_a_record_carries_stable_identity_and_utc_timestamp() -> None:
    record = extract_usage_record(usage_event())

    assert record is not None
    assert record.platform == PLATFORM
    assert record.session_id == SES_DEFAULT_ID
    assert record.message_id == RESPONSE_DEFAULT_ID
    assert record.source_event_id == f"{SES_DEFAULT_ID}:{RESPONSE_DEFAULT_ID}"
    assert record.timestamp.tzinfo is not None
    assert record.timestamp == datetime(2026, 9, 22, 12, 53, 47, 767_000, tzinfo=timezone.utc)


# --- token field mapping ---


def test_six_usage_fields_map_to_the_four_token_categories() -> None:
    record = extract_usage_record(usage_event())

    assert record is not None
    assert record.input_tokens == 100
    assert record.output_tokens == 20
    assert record.cache_read_tokens == 40
    assert record.cache_write_tokens == 0
    assert record.reasoning_tokens == 5
    assert record.total_tokens == 120  # input + output, matching Codex's own total


def test_cache_read_is_a_subset_of_input_not_an_addition() -> None:
    """`subset_of_input` keeps 40 cached tokens from being added to the 100 input."""
    record = extract_usage_record(usage_event())

    assert record is not None
    assert record.cache_overlap == "subset_of_input"
    assert record.total_tokens == 120  # not 160
    # consumption skips overlapping categories: input + output only.
    assert record.consumption_tokens == 120


def test_reasoning_is_a_subset_of_output_not_an_addition() -> None:
    record = extract_usage_record(usage_event())

    assert record is not None
    assert record.reasoning_overlap == "subset_of_output"
    assert record.reasoning_tokens == 5
    assert record.total_tokens == 120  # not 125


# --- provider and model attribution ---


def test_the_explicit_provider_from_session_meta_is_kept() -> None:
    record = extract_usage_record(usage_event(provider_id=PROVIDER_DEFAULT))

    assert record is not None
    assert record.provider_id == PROVIDER_DEFAULT
    assert record.model_id == MODEL_DEFAULT


def test_a_failed_model_join_reports_unknown() -> None:
    record = extract_usage_record(usage_event(model_id=None))

    assert record is not None
    assert record.model_id == UNKNOWN_VALUE
    assert record.usage_status == "reported"  # usage is intact even without a model


def test_a_failed_provider_join_reports_unknown() -> None:
    record = extract_usage_record(usage_event(provider_id=None))

    assert record is not None
    assert record.provider_id == UNKNOWN_VALUE


# --- defensive handling ---


def test_an_event_without_a_timestamp_is_skipped() -> None:
    assert extract_usage_record(usage_event(timestamp=None)) is None


def test_an_event_without_usage_is_stored_as_unavailable() -> None:
    record = extract_usage_record(usage_event(usage={}))

    assert record is not None
    assert record.usage_status == "unavailable"
    assert record.total_tokens is None
    assert record.input_tokens is None
