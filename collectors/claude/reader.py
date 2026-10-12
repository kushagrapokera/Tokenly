"""Read raw assistant records out of Claude Code session transcripts.

This module is the only place that knows Claude Code's JSONL layout.
Everything above it works with the plain Python shapes defined here, so a
layout change fails loudly in the learning tests rather than silently
skewing totals.

Layout pinned by these reads (verified against Claude Code 2.1.278/2.1.282,
documented in `docs/claude_storage_analysis.md`):

  `projects/<encoded-cwd>/<session-uuid>.jsonl`  - one file per session
  assistant line:
    {type: "assistant", message: {id, role, model, usage{...}}, uuid,
     timestamp: ISO-8601 UTC, sessionId, isSidechain}

Only `type == "assistant"` lines carry usage. A session's file stem equals
its `sessionId`, and one request (`message.id`) can occupy several lines
(one per streamed content block) with identical usage values — the reader
yields every line and lets the extractor decide identity, mirroring how the
OpenCode reader yields rows and the extractor defers incomplete ones.
"""

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

ASSISTANT_TYPE = "assistant"
ASSISTANT_ROLE = "assistant"


@dataclass(frozen=True)
class SessionFile:
    """One Claude Code session transcript on disk."""

    session_id: str
    project_directory: str
    path: Path


@dataclass(frozen=True)
class AssistantRecord:
    """One assistant line from a session transcript, already shaped."""

    session_id: str
    message_id: str | None
    model_id: str | None
    timestamp: datetime | None
    usage: dict[str, Any]
    raw_payload: dict[str, Any]


def list_session_files(projects_directory: Path) -> list[SessionFile]:
    """Return every session transcript found under the projects directory.

    The session id comes from the filename stem, which equals the `sessionId`
    on every line (verified across the store). A directory whose files cannot
    be listed is logged and skipped rather than aborting discovery.
    """
    if not projects_directory.is_dir():
        return []
    sessions: list[SessionFile] = []
    for project_directory in sorted(projects_directory.iterdir()):
        if not project_directory.is_dir():
            continue
        for transcript_path in sorted(project_directory.glob("*.jsonl")):
            sessions.append(
                SessionFile(
                    session_id=transcript_path.stem,
                    project_directory=project_directory.name,
                    path=transcript_path,
                )
            )
    return sessions


def iter_assistant_records(session_file: SessionFile) -> Iterator[AssistantRecord]:
    """Yield every assistant line of one transcript in stored order.

    Unparseable lines are logged and skipped: one corrupt or half-written
    line must not abort a whole history import. Lines that are not
    assistant-role records are filtered here so the extractor sees only
    what carries usage.
    """
    try:
        lines = session_file.path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        logger.warning(
            "skipping claude session %s: cannot read %s (%s)",
            session_file.session_id,
            session_file.path,
            error,
        )
        return

    for line in lines:
        if not line.strip():
            continue
        decoded = _decode_line(line, session_file)
        if decoded is None:
            continue
        payload, message, usage = decoded
        if message.get("role") != ASSISTANT_ROLE:
            continue
        _warn_on_unexpected_session_line(session_file, payload)
        yield _to_record(session_file, payload, message, usage)


def _decode_line(
    line: str, session_file: SessionFile
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    """Parse one JSONL line, or None when it is not readable JSON."""
    try:
        decoded = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("skipping a non-JSON line in session %s", session_file.session_id)
        return None
    if not isinstance(decoded, dict):
        logger.warning("skipping a non-object line in session %s", session_file.session_id)
        return None
    payload = cast(dict[str, Any], decoded)
    if payload.get("type") != ASSISTANT_TYPE:
        return None
    message = _mapping(payload.get("message"))
    usage = _mapping(message.get("usage"))
    return payload, message, usage


def _to_record(
    session_file: SessionFile,
    payload: dict[str, Any],
    message: dict[str, Any],
    usage: dict[str, Any],
) -> AssistantRecord:
    """Shape one decoded assistant line for the extractor."""
    return AssistantRecord(
        session_id=session_file.session_id,
        message_id=_text_or_none(message.get("id")),
        model_id=_text_or_none(message.get("model")),
        timestamp=_read_timestamp(_text_or_none(payload.get("timestamp"))),
        usage=usage,
        raw_payload=payload,
    )


def _read_timestamp(iso_text: str | None) -> datetime | None:
    """Parse an ISO-8601 UTC timestamp; None when absent or unreadable."""
    if not iso_text:
        return None
    try:
        return datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("skipping a line with an unreadable timestamp %r", iso_text)
        return None


def _warn_on_unexpected_session_line(session_file: SessionFile, payload: dict[str, Any]) -> None:
    """Warn when a line's sessionId disagrees with its transcript file.

    The collector keys events by the filename's session id, so a mismatch
    would misattribute usage; warning makes that visible instead of silent.
    """
    claimed = _text_or_none(
        payload.get("sessionId") or payload.get("session_id")
    )
    if claimed and claimed != session_file.session_id:
        logger.warning(
            "session file %s carries a line claiming session id %s (file stem %s)",
            session_file.path.name,
            claimed,
            session_file.session_id,
        )


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
