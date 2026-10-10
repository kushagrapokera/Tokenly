"""Turn raw OpenCode message rows into normalized usage records.

This module reads OpenCode's own fields and hands the token payload to
`normalization`, which decides how the categories combine. Keeping the two apart means
the overlap rules are written once and any future platform reuses them.

Two rules come straight from the Phase 1 analysis:

  * `message.id` is the stable dedup key; `parentID` is not (sibling steps share one).
  * A message whose `time` has no `completed` is still generating, so it is not a usage
    event yet. It gets picked up on a later scan, keyed by the same `message.id`.
"""

import logging
from datetime import datetime, timezone
from typing import Any, cast

from collectors.opencode.reader import MessageRow
from errors.exceptions import CollectorError
from normalization.categories import OPENCODE_RELATIONSHIPS
from normalization.normalizer import normalize_usage_record
from schemas.usage import UsageRecord

logger = logging.getLogger(__name__)

PLATFORM = "opencode"


class MalformedMessageError(CollectorError):
    """Raised when a message row lacks the fields every usage record requires."""

    def __init__(self, message_id: str, missing_field: str) -> None:
        super().__init__(f"message {message_id} is missing required field {missing_field!r}")
        self.message_id = message_id
        self.missing_field = missing_field


def extract_usage_record(row: MessageRow) -> UsageRecord | None:
    """Return the usage record for one assistant message, or None when it is still running."""
    if not is_completed(row):
        logger.debug("message %s has not completed yet; deferring to a later scan", row.message_id)
        return None

    raw_tokens = read_tokens(row)
    return normalize_usage_record(
        platform=PLATFORM,
        provider_id=require_text(row, "providerID"),
        model_id=require_text(row, "modelID"),
        session_id=row.session_id,
        message_id=row.message_id,
        source_event_id=row.message_id,
        timestamp=read_timestamp(row),
        raw_tokens=raw_tokens or {},
        raw_usage=read_raw_usage(row, raw_tokens),
        relationships=OPENCODE_RELATIONSHIPS,
    )


def is_completed(row: MessageRow) -> bool:
    """Report whether OpenCode finished generating this message."""
    time_block = read_mapping(row.data.get("time"))
    return time_block.get("completed") is not None


def read_timestamp(row: MessageRow) -> datetime:
    """Return the message's creation time as an aware UTC datetime.

    `data.time.created` is authoritative; the `time_created` column agreed on every one
    of the 1,748 live rows, so it is only a fallback for rows missing the JSON field.
    """
    time_block = read_mapping(row.data.get("time"))
    created_ms = time_block.get("created")
    if not isinstance(created_ms, int):
        return datetime.fromtimestamp(row.time_created_ms / 1000, tz=timezone.utc)
    return datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)


def read_tokens(row: MessageRow) -> dict[str, Any] | None:
    """Return the message's token payload, or None when OpenCode reported no usage."""
    tokens = row.data.get("tokens")
    if not isinstance(tokens, dict):
        if tokens is not None:
            logger.warning(
                "message %s has a non-object 'tokens' value (%s); treating usage as unavailable",
                row.message_id,
                type(tokens).__name__,
            )
        return None
    return cast(dict[str, Any], tokens)


def read_raw_usage(row: MessageRow, raw_tokens: dict[str, Any] | None) -> dict[str, Any]:
    """Preserve the original token metadata plus terminal outcome for later phases."""
    error = row.data.get("error")
    finish = row.data.get("finish")
    variant = row.data.get("variant")
    return {
        "tokens": raw_tokens,
        "reported_total": (raw_tokens or {}).get("total"),
        "finish": finish if isinstance(finish, str) else None,
        "error": error.get("name") if isinstance(error, dict) else None,
        "variant": variant if isinstance(variant, str) else None,
    }


def require_text(row: MessageRow, key: str) -> str:
    """Read a required non-empty string field or raise MalformedMessageError."""
    value = row.data.get(key)
    if not isinstance(value, str) or not value:
        raise MalformedMessageError(row.message_id, key)
    return value


def read_mapping(value: object) -> dict[str, Any]:
    """Return value when it is a dict, otherwise an empty dict."""
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}
