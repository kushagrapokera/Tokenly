"""Turn raw Claude Code assistant lines into normalized usage records.

This module reads Claude Code's own fields and hands the token payload to
`normalization`, which decides how the categories combine — the same split
the OpenCode and Cline extractors follow.

Rules straight from the Phase 2 analysis (`docs/claude_storage_analysis.md`):

  * Claude Code writes several JSONL lines per model request, one per streamed
    content block, all carrying the same `message.id` and identical usage.
    One usage event is one distinct `(session_id, message.id)`; collapsing by
    that identity is mandatory — summing lines would triple-count.
  * `usage.input_tokens` excludes cached prompt tokens, so cache reads and
    writes are additive categories for the consumption total (Anthropic's
    own reporting separates them); the shared `CLAUDE_RELATIONSHIPS` records
    this once, where every platform's overlap data lives.
  * `message.usage` missing yields an `unavailable` record, never a zero.
  * The provider has no first-class field; attribution follows the rules in
    `collectors.claude.providers` (prefix namespaces, the two documented
    Bedrock/Vertex id shapes, then honest `unknown`).
"""

import logging
from typing import Any, cast

from collectors.claude.providers import infer_provider_id
from collectors.claude.reader import AssistantRecord
from errors.exceptions import CollectorError
from normalization.categories import CLAUDE_RELATIONSHIPS
from normalization.normalizer import normalize_usage_record
from schemas.usage import UsageRecord

logger = logging.getLogger(__name__)

PLATFORM = "claude_code"

UNKNOWN_MODEL = "unknown"

__all__ = [
    "UNKNOWN_MODEL",
    "PLATFORM",
    "MalformedAssistantError",
    "extract_usage_record",
    "infer_provider_id",
    "namespaced_event_id",
    "read_raw_usage",
    "read_tokens",
]


class MalformedAssistantError(CollectorError):
    """Raised when an assistant line lacks the fields every record requires."""

    def __init__(self, session_id: str, missing_field: str) -> None:
        super().__init__(
            f"assistant line in session {session_id} is missing required field {missing_field!r}"
        )
        self.session_id = session_id
        self.missing_field = missing_field


def namespaced_event_id(session_id: str, message_id: str) -> str:
    """Return the dedup key that stays unique across sessions and platforms.

    Bare `message.id` is not safe: sessions can be resumed into a new file
    carrying the same ids, and OpenCode/Cline use different id shapes that
    could collide. The session namespace keeps both apart, matching the
    Cline convention Phase 1 pinned.
    """
    return f"{session_id}:{message_id}"


def extract_usage_record(record: AssistantRecord) -> UsageRecord | None:
    """Return the usage record for one assistant line, or None when unusable.

    Repeated lines of one model request yield equal records (same identity,
    same counts), so the caller may collapse them or leave the upsert to
    deduplicate — both produce exactly one stored row.
    """
    message_id = record.message_id
    if message_id is None:
        logger.warning(
            "skipping assistant line in session %s: missing message id", record.session_id
        )
        return None
    model_id = record.model_id
    if model_id is None:
        model_id = UNKNOWN_MODEL
        logger.debug("assistant line %s has no model; attributing to %r", message_id, model_id)
    if record.timestamp is None:
        logger.warning("skipping assistant line %s: missing timestamp", message_id)
        return None

    raw_tokens = read_tokens(record)
    return normalize_usage_record(
        platform=PLATFORM,
        provider_id=infer_provider_id(model_id),
        model_id=model_id,
        session_id=record.session_id,
        message_id=message_id,
        source_event_id=namespaced_event_id(record.session_id, message_id),
        timestamp=record.timestamp,
        raw_tokens=raw_tokens or {},
        raw_usage=read_raw_usage(record, raw_tokens),
        relationships=CLAUDE_RELATIONSHIPS,
    )


def read_tokens(record: AssistantRecord) -> dict[str, Any] | None:
    """Return the line's token payload, or None when Claude reported no usage."""
    usage = record.usage
    if not usage:
        return None
    details = _mapping(usage.get("output_tokens_details"))
    return {
        "input": usage.get("input_tokens"),
        "output": usage.get("output_tokens"),
        "reasoning": details.get("thinking_tokens"),
        "cache": {
            "read": usage.get("cache_read_input_tokens"),
            "write": usage.get("cache_creation_input_tokens"),
        },
    }


def read_raw_usage(
    record: AssistantRecord, raw_tokens: dict[str, Any] | None
) -> dict[str, Any]:
    """Preserve original metadata for later phases, without message contents."""
    usage = record.usage or {}
    cache_creation = _mapping(usage.get("cache_creation"))
    return {
        "usage": raw_tokens,
        "stop_reason": _text_or_none(_assistant_message(record).get("stop_reason")),
        "service_tier": _text_or_none(usage.get("service_tier")),
        "cache_ttl_split": {
            key: cache_creation.get(key)
            for key in ("ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens")
        },
        "is_sidechain": record.raw_payload.get("isSidechain"),
        "api_block_count": None,  # collapsed caller-side; per-line payload not kept
        "claude_version": _text_or_none(record.raw_payload.get("version")),
    }


def _assistant_message(record: AssistantRecord) -> dict[str, Any]:
    """The assistant line's inner `message` object."""
    return _mapping(record.raw_payload.get("message"))


def _mapping(value: object) -> dict[str, Any]:
    """Return value when it is a dict, otherwise an empty dict."""
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _text_or_none(value: object) -> str | None:
    """Return a non-empty string value, or None."""
    if isinstance(value, str) and value:
        return value
    return None
