"""Turn raw OpenCode message rows into normalized usage records.

Extraction only. Deciding how overlapping token categories combine is Phase 4's job;
here we read each field faithfully, preserve the raw token payload so nothing is lost,
and classify what we found. Two rules come straight from the Phase 1 analysis:

  * `message.id` is the stable dedup key; `parentID` is not (sibling steps share one).
  * A message whose `time` has no `completed` is still generating, so it is not a usage
    event yet. It gets picked up on a later scan, keyed by the same `message.id`.
"""

import logging
from datetime import datetime, timezone
from typing import Any, cast

from collectors.opencode.reader import MessageRow
from errors.exceptions import CollectorError
from schemas.usage import UsageRecord, UsageStatus

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

    provider_id = require_text(row, "providerID")
    model_id = require_text(row, "modelID")
    raw_tokens = read_tokens(row)
    input_tokens, output_tokens = extract_base_token_counts(row, raw_tokens)
    usage_status: UsageStatus = "reported" if raw_tokens is not None else "unavailable"

    return UsageRecord(
        platform=PLATFORM,
        provider_id=provider_id,
        model_id=model_id,
        session_id=row.session_id,
        message_id=row.message_id,
        source_event_id=row.message_id,
        timestamp=read_timestamp(row),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=compute_total(input_tokens, output_tokens),
        usage_status=usage_status,
        raw_usage=read_raw_usage(row, raw_tokens),
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


def extract_base_token_counts(
    row: MessageRow, raw_tokens: dict[str, Any] | None
) -> tuple[int | None, int | None]:
    """Return (input, output) token counts, or (None, None) when usage is unavailable.

    Only `input` and `output` are read. `reasoning` and `cache` are overlapping
    sub-categories that must never be folded into the totals by this layer.
    """
    if raw_tokens is None:
        return None, None

    input_tokens = read_token_count(raw_tokens, "input", row.message_id)
    output_tokens = read_token_count(raw_tokens, "output", row.message_id)
    return input_tokens, output_tokens


def read_token_count(raw_tokens: dict[str, Any], key: str, message_id: str) -> int | None:
    """Read one nonnegative integer token count; None when absent or nonsensical."""
    value = raw_tokens.get(key)
    if value is None:
        logger.warning("message %s has no %r token count", message_id, key)
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        logger.warning("message %s has a non-integer %r token count: %r", message_id, key, value)
        return None
    if value < 0:
        logger.warning("message %s has a negative %r token count: %r", message_id, key, value)
        return None
    return value


def compute_total(input_tokens: int | None, output_tokens: int | None) -> int | None:
    """Sum input and output, the two non-overlapping categories.

    OpenCode's own `tokens.total` also folds in reasoning and cache reads — 1,258 of
    1,271 live rows matched `input + output + reasoning + cache.read`, not
    `input + output` — so it is never used. A total is emitted only when both inputs
    are known; missing values are never invented.
    """
    if input_tokens is None or output_tokens is None:
        return None
    return input_tokens + output_tokens


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
