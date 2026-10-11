"""Tests for turning raw Cline messages into normalized usage records."""

import pytest

from collectors.cline.extractor import (
    MalformedMessageError,
    extract_usage_record,
    namespaced_event_id,
)
from collectors.cline.reader import MessageRow

CREATED_MS = 1_790_495_317_187


def make_row(data: dict[str, object], message_id: str = "msg_0001") -> MessageRow:
    """Build a MessageRow without needing session files."""
    return MessageRow(
        message_id=message_id,
        session_id="ses_0001",
        time_created_ms=CREATED_MS,
        data=data,
    )


def assistant_message(**overrides: object) -> dict[str, object]:
    """A minimal complete assistant message payload."""
    message: dict[str, object] = {
        "id": "msg_0001",
        "role": "assistant",
        "content": [{"type": "text", "text": "done"}],
        "ts": CREATED_MS,
        "modelInfo": {"id": "cline-free/gemini-3.8-flash", "provider": "cline"},
        "metrics": {
            "inputTokens": 3989,
            "outputTokens": 113,
            "cacheReadTokens": 50,
            "cacheWriteTokens": 0,
        },
    }
    message.update(overrides)
    return message


def test_record_carries_provider_model_and_session_identity() -> None:
    record = extract_usage_record(make_row(assistant_message()))

    assert record is not None
    assert record.platform == "cline"
    assert record.provider_id == "cline"
    assert record.model_id == "cline-free/gemini-3.8-flash"
    assert record.session_id == "ses_0001"
    assert record.message_id == "msg_0001"


def test_source_event_id_is_namespaced_by_session() -> None:
    """Phase 1: bare message ids repeat across resume pairs — namespace them."""
    record = extract_usage_record(make_row(assistant_message()))

    assert record is not None
    assert record.source_event_id == namespaced_event_id("ses_0001", "msg_0001")
    assert record.source_event_id == "ses_0001:msg_0001"


def test_token_fields_follow_the_phase_1_field_map() -> None:
    record = extract_usage_record(make_row(assistant_message()))

    assert record is not None
    assert record.input_tokens == 3989
    assert record.output_tokens == 113
    assert record.cache_read_tokens == 50
    assert record.cache_write_tokens == 0
    assert record.total_tokens == 3989 + 113


def test_consumption_adds_the_cache_categories() -> None:
    record = extract_usage_record(make_row(assistant_message()))

    assert record is not None
    assert record.consumption_tokens == 3989 + 113 + 50


def test_error_display_without_metrics_is_unavailable_not_zero() -> None:
    row = make_row(
        assistant_message(metrics=None) if False else _error_message(),
        message_id="error_0001",
    )

    record = extract_usage_record(row)

    assert record is not None
    assert record.usage_status == "unavailable"
    assert record.input_tokens is None
    assert record.output_tokens is None
    assert record.total_tokens is None


def _error_message() -> dict[str, object]:
    return {
        "id": "error_0001",
        "role": "assistant",
        "content": [{"type": "text", "text": "Daily free limit reached"}],
        "ts": CREATED_MS,
        "modelInfo": {"id": "cline-free/gemini-3.8-flash", "provider": "cline"},
        "metadata": {"displayOnly": True, "displayRole": "error"},
    }


def test_thinking_only_message_without_metrics_is_unavailable() -> None:
    payload = assistant_message(
        content=[{"type": "thinking", "thinking": "planning"}],
    )
    del payload["metrics"]

    record = extract_usage_record(make_row(payload))

    assert record is not None
    assert record.usage_status == "unavailable"


def test_user_message_yields_no_record() -> None:
    row = make_row({"id": "user_1", "role": "user", "ts": CREATED_MS}, message_id="user_1")

    assert extract_usage_record(row) is None


@pytest.mark.parametrize("missing_key", ["provider", "id"])
def test_missing_model_info_field_raises_a_named_error(missing_key: str) -> None:
    model_info = {"id": "cline-free/gemini-3.8-flash", "provider": "cline"}
    del model_info[missing_key]
    row = make_row(assistant_message(modelInfo=model_info))

    with pytest.raises(MalformedMessageError) as caught:
        extract_usage_record(row)

    assert caught.value.missing_field == f"modelInfo.{missing_key}"


def test_missing_model_info_block_raises_a_named_error() -> None:
    payload = assistant_message()
    del payload["modelInfo"]
    row = make_row(payload)

    with pytest.raises(MalformedMessageError):
        extract_usage_record(row)
