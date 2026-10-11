"""Turn raw Codex usage events into normalized usage records.

The field map comes from `docs/codex_storage_analysis.md` §4 and §9:

* **Identity** — dedup key is `{session_id}:{response_id}`. `response_id` is unique
  per API call (verified: 229 records, 229 distinct keys in the live store), so it
  doubles as the `message_id`.
* **Tokens** — only the per-call `usage` scope is ingested. `turn_token_usage` and
  `thread_token_usage` are cumulative rollups that must never be summed (the same
  trap as Claude's `cost-state` and Cline's `metadata.usage`).
* **Relationships** — `cached_input_tokens` and `reasoning_output_tokens` are
  subsets of input/output, so `CODEX_RELATIONSHIPS` keeps them out of consumption
  to avoid double counting the total.
* **Model / provider** — the provider is the explicit `session_meta.model_provider`
  (rule 1: prefer first-class metadata), the model is joined from `turn_context` on
  `turn_id`; a failed join reports `unknown` rather than guessing.
"""

import logging
from typing import Any

from collectors.codex.providers import resolve_provider_id
from collectors.codex.reader import CodexUsageEvent
from normalization.categories import CODEX_RELATIONSHIPS
from normalization.normalizer import normalize_usage_record
from schemas.usage import UsageRecord

logger = logging.getLogger(__name__)

PLATFORM = "codex"
UNKNOWN_VALUE = "unknown"

# Which of Codex's three usage scopes this record was built from; recorded in
# `raw_usage` so a reconciliation test can prove rollups were never mixed in.
USAGE_SCOPE = "usage"


def namespaced_event_id(session_id: str, response_id: str) -> str:
    """Build the globally-unique dedup key for one Codex usage event."""
    return f"{session_id}:{response_id}"


def extract_usage_record(event: CodexUsageEvent) -> UsageRecord | None:
    """Map one usage event onto the shared record; None when identity/timestamp is unusable."""
    if event.timestamp is None:
        logger.warning(
            "skipping codex usage event %s in session %s: missing timestamp",
            event.response_id,
            event.session_id,
        )
        return None

    model_id = event.model_id or UNKNOWN_VALUE
    # Provider follows §5.3: the recorded `model_provider` (canonicalised, unknowns
    # preserved) first, else an explicit gateway prefix on the model, else `unknown`.
    provider_id = resolve_provider_id(event.provider_id, event.model_id)
    raw_tokens = read_tokens(event)

    return normalize_usage_record(
        platform=PLATFORM,
        provider_id=provider_id,
        model_id=model_id,
        session_id=event.session_id,
        message_id=event.response_id,
        source_event_id=namespaced_event_id(event.session_id, event.response_id),
        timestamp=event.timestamp,
        raw_tokens=raw_tokens,
        raw_usage=read_raw_usage(event),
        relationships=CODEX_RELATIONSHIPS,
    )


def read_tokens(event: CodexUsageEvent) -> dict[str, Any]:
    """Project Codex's six usage fields onto the shared token categories."""
    usage = event.usage
    return {
        "input": usage.get("input_tokens"),
        "output": usage.get("output_tokens"),
        "reasoning": usage.get("reasoning_output_tokens"),
        "cache": {
            "read": usage.get("cached_input_tokens"),
            "write": usage.get("cache_write_input_tokens"),
        },
    }


def read_raw_usage(event: CodexUsageEvent) -> dict[str, Any]:
    """Keep the provenance a user needs, with no prompt or response content (privacy)."""
    return {
        "usage": event.usage,
        "scope": USAGE_SCOPE,
        "turn_id": event.turn_id,
        "model_provider": event.provider_id,
        "cli_version": event.cli_version,
    }
