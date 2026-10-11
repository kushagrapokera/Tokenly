"""Read raw usage events out of Codex CLI's rollout session files.

This module is the only place that knows Codex's JSONL layout. Everything above it
works with the plain Python shapes defined here, so a layout change fails loudly in
the learning tests rather than silently skewing totals.

Layout pinned against Codex CLI 0.155.1 (documented in
`docs/codex_storage_analysis.md` §3 and §4):

* Files live at `sessions/YYYY/MM/DD/rollout-<timestamp>-<session-uuid>.jsonl`.
* Every line is an envelope: `{"timestamp": ISO-8601, "ordinal": int, "type": str,
  "payload": {...}}`.
* The six observed top-level `type` values are `session_meta`, `event_msg`,
  `response_item`, `world_state`, `turn_context`, and `token_usage_record`.
* Only `token_usage_record` carries usage. Its payload holds three scopes: `usage`
  (per API call), `turn_token_usage` (per turn, cumulative), and
  `thread_token_usage` (per session, cumulative). This reader emits the per-call
  `usage` scope only — summing the other two would multiply every figure.
* Model attribution joins `token_usage_record.payload.turn_id` to the
  `turn_context` line's `payload.model`; the provider comes from
  `session_meta.payload.model_provider`.
"""

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SESSION_META_TYPE = "session_meta"
TURN_CONTEXT_TYPE = "turn_context"
TOKEN_USAGE_RECORD_TYPE = "token_usage_record"

ROLLOUT_GLOB = "rollout-*.jsonl"

# The only line types this reader needs; every other type is a transcript detail
# that carries no usage.
_INTERESTING_TYPES = frozenset({SESSION_META_TYPE, TURN_CONTEXT_TYPE, TOKEN_USAGE_RECORD_TYPE})


@dataclass(frozen=True)
class RolloutFile:
    """One rollout session file found under the sessions directory."""

    path: Path

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class CodexUsageEvent:
    """One per-call usage record, already joined to its model and provider.

    `usage` is the per-call object exactly as written (the six Codex fields);
    `raw_payload` is the whole `token_usage_record` payload for provenance.
    `model_id` / `provider_id` are None when the join could not be made, which the
    extractor records under the `unknown` bucket.
    """

    session_id: str
    turn_id: str
    response_id: str
    timestamp: datetime | None
    model_id: str | None
    provider_id: str | None
    usage: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    cli_version: str | None = None


def list_rollout_files(sessions_directory: Path) -> list[RolloutFile]:
    """Return every `rollout-*.jsonl` file under the sessions directory, sorted."""
    if not sessions_directory.is_dir():
        logger.debug("sessions directory %s does not exist", sessions_directory)
        return []
    files = sorted(sessions_directory.rglob(ROLLOUT_GLOB))
    return [RolloutFile(path) for path in files if path.is_file()]


def iter_usage_events(rollout: RolloutFile) -> Iterator[CodexUsageEvent]:
    """Yield each per-call usage event from one rollout file, model/provider joined.

    A corrupt or non-JSON line is logged and skipped rather than aborting the file,
    matching the other collectors' tolerance for partially-written sessions.
    """
    lines = _load_usage_lines(rollout)
    provider_id, cli_version, file_session_id = _read_session_context(lines)
    model_by_turn = _read_model_by_turn(lines)

    for envelope, payload in lines:
        if envelope.get("type") != TOKEN_USAGE_RECORD_TYPE:
            continue
        event = _to_usage_event(
            envelope=envelope,
            payload=payload,
            model_by_turn=model_by_turn,
            provider_id=provider_id,
            cli_version=cli_version,
            file_session_id=file_session_id,
            rollout=rollout,
        )
        if event is not None:
            yield event


# --- line decoding ---


def _load_usage_lines(rollout: RolloutFile) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Decode a rollout file into `(envelope, payload)` pairs for the types we read."""
    try:
        text = rollout.path.read_text(encoding="utf-8")
    except OSError as error:
        logger.warning("cannot read rollout file %s: %s", rollout.path, error)
        return []

    decoded: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("skipping a non-JSON line %d in %s", line_number, rollout.name)
            continue
        if not isinstance(envelope, dict):
            logger.warning("skipping a non-object line %d in %s", line_number, rollout.name)
            continue
        line_type = envelope.get("type")
        if line_type not in _INTERESTING_TYPES:
            continue
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            logger.warning(
                "skipping %s line %d without an object payload in %s",
                line_type,
                line_number,
                rollout.name,
            )
            continue
        decoded.append((envelope, payload))
    return decoded


# --- session-level context (model_provider, cli_version, session id) ---


def _read_session_context(
    lines: list[tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[str | None, str | None, str | None]:
    """Return `(model_provider, cli_version, session_id)` from the `session_meta` line."""
    provider_id: str | None = None
    cli_version: str | None = None
    session_id: str | None = None
    for envelope, payload in lines:
        if envelope.get("type") != SESSION_META_TYPE:
            continue
        provider_id = _text(payload.get("model_provider"))
        cli_version = _text(payload.get("cli_version"))
        session_id = _text(payload.get("session_id")) or _text(payload.get("id"))
        break
    return provider_id, cli_version, session_id



# --- token_usage_record -> CodexUsageEvent ---


def _to_usage_event(
    *,
    envelope: dict[str, Any],
    payload: dict[str, Any],
    model_by_turn: dict[str, str],
    provider_id: str | None,
    cli_version: str | None,
    file_session_id: str | None,
    rollout: RolloutFile,
) -> CodexUsageEvent | None:
    """Build one usage event; return None (with a log) if identity is unusable."""
    session_id = _text(payload.get("session_id")) or file_session_id
    response_id = _text(payload.get("response_id"))
    if not session_id or not response_id:
        logger.warning(
            "skipping a token_usage_record in %s: missing session_id or response_id",
            rollout.name,
        )
        return None

    turn_id = _text(payload.get("turn_id")) or ""
    usage = payload.get("usage")
    return CodexUsageEvent(
        session_id=session_id,
        turn_id=turn_id,
        response_id=response_id,
        timestamp=_read_timestamp(_text(envelope.get("timestamp"))),
        model_id=model_by_turn.get(turn_id),
        provider_id=provider_id,
        usage=usage if isinstance(usage, dict) else {},
        raw_payload=payload,
        cli_version=cli_version,
    )


# --- shared helpers ---


def _text(value: Any) -> str | None:
    """Return a non-empty string, or None for anything else."""
    if isinstance(value, str) and value:
        return value
    return None


def _read_timestamp(raw: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into an aware UTC datetime; None if unusable."""
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("unparseable rollout timestamp %r", raw)
        return None
    if parsed.tzinfo is None:
        # Codex always writes a trailing `Z`; assume UTC if a build ever omits it.
        return parsed.replace(tzinfo=timezone.utc)
    return parsed

# --- per-turn model join ---


def _read_model_by_turn(
    lines: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, str]:
    """Map `turn_id` -> `model` from every `turn_context` line in the file."""
    model_by_turn: dict[str, str] = {}
    for envelope, payload in lines:
        if envelope.get("type") != TURN_CONTEXT_TYPE:
            continue
        turn_id = _text(payload.get("turn_id"))
        model = _text(payload.get("model"))
        if turn_id and model:
            model_by_turn[turn_id] = model
    return model_by_turn
