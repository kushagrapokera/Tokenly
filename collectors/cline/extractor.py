"""Turn raw Cline message rows into normalized usage records.

This module reads Cline's own fields and hands the token payload to
`normalization`, which decides how the categories combine. Keeping the two
apart means the overlap rules are written once and every platform reuses them.

Rules straight from the Phase 1 analysis (`docs/cline_storage_analysis.md`):

  * `{session_id}:{message.id}` is the stable dedup key. Bare `message.id`
    is not: 108 ids repeat across a failed→completed resume pair, and
    OpenCode uses `msg_*` ids too.
  * A message carrying a `metrics` object is one usage event. A message
    without one (error displays, thinking-only) is an `unavailable` record,
    never a zero.
  * Session `metadata.usage` rollups are never ingested — they equal the
    per-message sums, so reading both would double every figure.
"""

import logging
from datetime import datetime, timezone
from typing import Any, cast

from collectors.cline.reader import ASSISTANT_ROLE, MessageRow
from errors.exceptions import CollectorError
from normalization.categories import CLINE_RELATIONSHIPS
from normalization.normalizer import normalize_usage_record
from schemas.usage import UsageRecord

logger = logging.getLogger(__name__)

PLATFORM = "cline"


class MalformedMessageError(CollectorError):
    """Raised when a message row lacks the fields every usage record requires."""

    def __init__(self, message_id: str, missing_field: str) -> None:
        super().__init__(f"message {message_id} is missing required field {missing_field!r}")
        self.message_id = message_id
        self.missing_field = missing_field


def namespaced_event_id(session_id: str, message_id: str) -> str:
    """Return the dedup key that stays unique across sessions and platforms."""
    return f"{session_id}:{message_id}"


def extract_usage_record(row: MessageRow) -> UsageRecord | None:
    """Return the usage record for one message, or None when it is not a model call."""
    if row.data.get("role") != ASSISTANT_ROLE:
        return None
    raw_tokens = read_tokens(row)
    provider_id = read_model_info(row, "provider")
    model_id = read_model_info(row, "id")
    return normalize_usage_record(
        platform=PLATFORM,
        provider_id=provider_id,
        model_id=model_id,
        session_id=row.session_id,
        message_id=row.message_id,
        source_event_id=namespaced_event_id(row.session_id, row.message_id),
        timestamp=read_timestamp(row),
        raw_tokens=raw_tokens or {},
        raw_usage=read_raw_usage(row, raw_tokens),
        relationships=CLINE_RELATIONSHIPS,
    )


def read_timestamp(row: MessageRow) -> datetime:
    """Return the message's `ts` as an aware UTC datetime."""
    return datetime.fromtimestamp(row.time_created_ms / 1000, tz=timezone.utc)


def read_tokens(row: MessageRow) -> dict[str, Any] | None:
    """Return the message's token payload, or None when Cline reported no usage."""
    metrics = row.data.get("metrics")
    if metrics is None:
        return None
    if not isinstance(metrics, dict):
        logger.warning(
            "message %s has a non-object 'metrics' value (%s); treating usage as unavailable",
            row.message_id,
            type(metrics).__name__,
        )
        return None
    payload = cast(dict[str, Any], metrics)
    return {
        "input": payload.get("inputTokens"),
        "output": payload.get("outputTokens"),
        "cache": {
            "read": payload.get("cacheReadTokens"),
            "write": payload.get("cacheWriteTokens"),
        },
    }


def read_raw_usage(row: MessageRow, raw_tokens: dict[str, Any] | None) -> dict[str, Any]:
    """Preserve the original token metadata plus terminal outcome for later phases."""
    metadata = row.data.get("metadata")
    metadata_mapping = cast(dict[str, Any], metadata) if isinstance(metadata, dict) else {}
    content_types: list[str] = []
    content = row.data.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("type"), str):
                content_types.append(str(block.get("type")))
    return {
        "metrics": row.data.get("metrics"),
        "display_role": metadata_mapping.get("displayRole"),
        "content_types": content_types,
        "raw_tokens_shape": sorted((raw_tokens or {}).keys()),
    }


def read_model_info(row: MessageRow, key: str) -> str:
    """Read a required non-empty `modelInfo` field or raise MalformedMessageError."""
    model_info = row.data.get("modelInfo")
    if not isinstance(model_info, dict):
        raise MalformedMessageError(row.message_id, f"modelInfo.{key}")
    value = cast(dict[str, Any], model_info).get(key)
    if not isinstance(value, str) or not value:
        raise MalformedMessageError(row.message_id, f"modelInfo.{key}")
    return value
