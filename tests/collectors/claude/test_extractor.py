"""Unit tests for the Claude Code extractor.

These drive the documented field map (`docs/claude_storage_analysis.md` §4,
§5, §7) through stand-in records built by the fixture, asserting the
normalized output the shared pipeline stores.
"""

from datetime import datetime, timezone
from typing import Any

import pytest

from collectors.claude.extractor import (
    PLATFORM,
    MalformedAssistantError,
    extract_usage_record,
    infer_provider_id,
    namespaced_event_id,
)
from collectors.claude.reader import AssistantRecord
from tests.collectors.claude.conftest import ClaudeStoreBuilder, _usage_payload

TIMESTAMP = "2026-09-22T11:52:31.580Z"


def assistant_record(
    store: ClaudeStoreBuilder,
    **overrides: object,
) -> AssistantRecord:
    """Build one standalone assistant record through the fixture's real shape."""
    message_id = "6a40154b-24ac-4fb7-9a44-58dcd7ee8ea2"
    session_id = "0d55869d-c59f-44ec-bdd5-fde7d17756ef"
    usage = _usage_payload(100, 20, 40, 0, 0)
    message_payload: dict[str, Any] = {
        "id": message_id,
        "role": "assistant",
        "model": "claude-sonnet-4-5",
        "usage": usage,
        "stop_reason": "end_turn",
    }
    payload: dict[str, Any] = {
        "type": "assistant",
        "message": message_payload,
        "timestamp": TIMESTAMP,
        "sessionId": session_id,
        "isSidechain": False,
        "version": "2.1.282",
    }
    for key, value in overrides.items():
        payload[key] = value
    return AssistantRecord(
        session_id=session_id,
        project_directory="-home-tester",
        message_id=message_payload["id"],
        model_id=message_payload.get("model"),
        timestamp=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")),
        usage=message_payload["usage"],
        raw_payload=payload,
    )


# --- platform and identity ---


def test_platform_is_claude_code() -> None:
    assert PLATFORM == "claude_code"


def test_event_id_is_namespaced_by_session() -> None:
    assert (
        namespaced_event_id("ses_a", "msg_1") == "ses_a:msg_1"
    )


def test_a_record_carries_stable_identity_and_utc_timestamp(
    claude_store: ClaudeStoreBuilder,
) -> None:
    assistant = assistant_record(claude_store)
    record = extract_usage_record(assistant)

    assert record is not None
    assert record.platform == PLATFORM
    assert record.session_id == "0d55869d-c59f-44ec-bdd5-fde7d17756ef"
    assert record.message_id == "6a40154b-24ac-4fb7-9a44-58dcd7ee8ea2"
    assert record.source_event_id == f"{record.session_id}:{record.message_id}"
    assert record.timestamp.tzinfo is not None
    assert record.timestamp == datetime(2026, 9, 22, 11, 52, 31, 580_000, tzinfo=timezone.utc)


# --- token field mapping ---


def test_usage_fields_map_to_the_four_token_categories(
    claude_store: ClaudeStoreBuilder,
) -> None:
    assistant = assistant_record(claude_store)
    record = extract_usage_record(assistant)

    assert record is not None
    assert record.input_tokens == 100
    assert record.output_tokens == 20
    assert record.cache_read_tokens == 40
    assert record.cache_write_tokens == 0
    assert record.total_tokens == 120


def test_cache_read_is_additive_to_consumption_but_not_to_the_total(
    claude_store: ClaudeStoreBuilder,
) -> None:
    assistant = assistant_record(claude_store)
    record = extract_usage_record(assistant)

    assert record is not None
    assert record.consumption_tokens == 160  # in + out + cache read
    assert record.total_tokens == 120
    assert record.cache_overlap == "additive"


def test_thinking_tokens_never_inflate_output(claude_store: ClaudeStoreBuilder) -> None:
    """Anthropic's thinking tokens are a breakdown of output, not extra."""
    from collectors.claude.reader import AssistantRecord

    assistant = AssistantRecord(
        session_id="ses",
        project_directory="proj",
        message_id="m1",
        model_id="claude-opus-4",
        timestamp=assistant_record(claude_store).timestamp,
        usage=_usage_payload(100, 5000, 0, 0, 3000),
        raw_payload={"message": {"usage": _usage_payload(100, 5000, 0, 0, 3000)}},
    )
    record = extract_usage_record(assistant)

    assert record is not None
    assert record.output_tokens == 5000
    assert record.total_tokens == 5100  # not 5100 + 3000
    assert record.reasoning_tokens == 3000
    assert record.reasoning_overlap == "subset_of_output"


# --- missing usage is unknown, never zero ---


def test_a_missing_usage_object_is_unavailable(claude_store: ClaudeStoreBuilder) -> None:
    from collectors.claude.reader import AssistantRecord

    assistant = AssistantRecord(
        session_id="ses",
        project_directory="proj",
        message_id="m1",
        model_id="claude-sonnet-4-5",
        timestamp=datetime(2026, 9, 22, 11, 52, 31, tzinfo=timezone.utc),
        usage={},
        raw_payload={"message": {"usage": None}},
    )
    record = extract_usage_record(assistant)

    assert record is not None
    assert record.usage_status == "unavailable"
    assert record.total_tokens is None
    assert record.input_tokens is None


# --- provider attribution ---


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("openrouter/deepseek/deepseek-chat", "openrouter"),
        ("bedrock/anthropic.claude-sonnet", "bedrock"),
        ("vertex/claude-3-5-sonnet", "vertex"),
        ("anthropic/claude-sonnet-4-5", "anthropic"),
        ("deepseek/deepseek-chat", "deepseek"),
        ("kimi/kimi-k2", "moonshot"),
        ("claude-sonnet-4-5", "unknown"),
        ("deepseek-flash", "unknown"),
    ],
)
def test_provider_inference_uses_prefixes_and_stays_unknown_otherwise(
    model_id: str, expected: str
) -> None:
    assert infer_provider_id(model_id) == expected


def test_a_bare_model_name_keeps_unknown_provider(claude_store: ClaudeStoreBuilder) -> None:
    assistant = assistant_record(claude_store)
    record = extract_usage_record(assistant)

    assert record is not None
    # The live store's `deepseek-flash` cannot be attributed to a gateway with
    # confidence, so the provider stays unknown rather than guessed.
    assert record.provider_id == "unknown"


def test_a_prefixed_model_names_its_gateway(claude_store: ClaudeStoreBuilder) -> None:
    from collectors.claude.reader import AssistantRecord

    assistant = AssistantRecord(
        session_id="ses",
        project_directory="proj",
        message_id="m2",
        model_id="openrouter/deepseek/deepseek-chat",
        timestamp=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc),
        usage=_usage_payload(90, 10, 0, 0, 0),
        raw_payload={"message": {"usage": _usage_payload(90, 10, 0, 0, 0)}},
    )
    record = extract_usage_record(assistant)

    assert record is not None
    assert record.provider_id == "openrouter"
    assert record.model_id == "openrouter/deepseek/deepseek-chat"


# --- defensive handling ---


def test_a_line_without_a_message_id_is_skipped(claude_store: ClaudeStoreBuilder) -> None:
    assistant = assistant_record(claude_store)
    object.__setattr__(assistant, "message_id", None)

    assert extract_usage_record(assistant) is None


def test_a_line_without_a_timestamp_is_skipped(claude_store: ClaudeStoreBuilder) -> None:
    assistant = assistant_record(claude_store)
    object.__setattr__(assistant, "timestamp", None)

    assert extract_usage_record(assistant) is None


def test_a_missing_model_is_reported_under_the_unknown_model(
    claude_store: ClaudeStoreBuilder,
) -> None:
    from collectors.claude.reader import AssistantRecord

    assistant = AssistantRecord(
        session_id="ses",
        project_directory="proj",
        message_id="m3",
        model_id=None,
        timestamp=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc),
        usage=_usage_payload(90, 10, 0, 0, 0),
        raw_payload={"message": {"usage": _usage_payload(90, 10, 0, 0, 0)}},
    )
    record = extract_usage_record(assistant)

    assert record is not None
    assert record.model_id == "unknown"
    assert record.usage_status == "reported"


def test_malformed_assistant_error_names_the_session() -> None:
    error = MalformedAssistantError("ses_1", "message.id")

    assert "ses_1" in str(error)
    assert "message.id" in str(error)
