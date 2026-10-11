"""Read raw session and message records out of Cline CLI's local store.

This module is the only place that knows Cline's storage shapes. Everything
above it works with the plain Python shapes defined here, so a schema change
fails loudly in the learning tests rather than silently skewing totals.

Shapes pinned by these reads (verified against Cline CLI 3.0.70, documented
in `docs/cline_storage_analysis.md`):

  sessions.db `sessions` table: (session_id, messages_path, metadata_json, ...)
  `<session_id>.messages.json`: {"version", "sessionId", "messages": [...]}
  assistant message: {id, role, ts, modelInfo{id, provider}, metrics?{...}}
"""

import json
import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from errors.exceptions import UnsupportedStorageFormatError

logger = logging.getLogger(__name__)

ASSISTANT_ROLE = "assistant"

_SESSIONS_QUERY = "SELECT session_id FROM sessions"

REQUIRED_TABLES = frozenset({"sessions"})


@dataclass(frozen=True)
class SessionRow:
    """One Cline session, as indexed in `sessions.db`.

    Only the id is carried. The index also stores a `messages_path`, but the
    collector rebuilds each session's file path from its id instead: the file
    naming is already pinned by `messages_file_for`, and a stale or empty
    column would otherwise silently point at the wrong file.
    """

    session_id: str


@dataclass(frozen=True)
class MessageRow:
    """One Cline message, with its JSON payload already decoded."""

    message_id: str
    session_id: str
    time_created_ms: int
    data: dict[str, Any]


def open_session_index(snapshot_path: Path) -> sqlite3.Connection:
    """Open a session-index snapshot read-only and confirm its tables."""
    connection = sqlite3.connect(f"file:{snapshot_path}?mode=ro", uri=True)
    verify_supported_schema(connection, snapshot_path)
    return connection


def verify_supported_schema(connection: sqlite3.Connection, snapshot_path: Path) -> None:
    """Raise UnsupportedStorageFormatError unless the snapshot has Cline's tables."""
    present = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = REQUIRED_TABLES - present
    if missing:
        raise UnsupportedStorageFormatError(
            str(snapshot_path), f"missing table(s): {', '.join(sorted(missing))}"
        )
    logger.debug("verified cline snapshot schema at %s", snapshot_path)


def list_sessions(connection: sqlite3.Connection) -> list[SessionRow]:
    """Return every indexed session."""
    return [SessionRow(session_id=str(row[0])) for row in connection.execute(_SESSIONS_QUERY)]


def session_ids_in_directory(sessions_directory: Path) -> list[str]:
    """Return session ids that have a directory on disk (orphan-dir tolerant).

    The db index can lag the filesystem (one orphan dir observed live), so
    discovery unions both sources rather than trusting either alone.
    """
    if not sessions_directory.is_dir():
        return []
    return sorted(entry.name for entry in sessions_directory.iterdir() if entry.is_dir())


def messages_file_for(sessions_directory: Path, session_id: str) -> Path:
    """Return the expected message-file path for one session."""
    return sessions_directory / session_id / f"{session_id}.messages.json"


def iter_session_messages(sessions_directory: Path, session_id: str) -> Iterator[MessageRow]:
    """Yield every message row of one session file in stored order.

    Files whose JSON is corrupt are logged and skipped: one bad file must not
    abort a whole history import. Messages missing an id, role, or timestamp
    are likewise skipped with a warning.
    """
    messages_path = messages_file_for(sessions_directory, session_id)
    try:
        payload = json.loads(messages_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning(
            "skipping cline session %s: cannot read %s (%s)", session_id, messages_path, error
        )
        return
    if not isinstance(payload, dict):
        logger.warning("skipping cline session %s: top-level JSON is not an object", session_id)
        return
    messages = payload.get("messages")
    if not isinstance(messages, list):
        logger.warning("skipping cline session %s: 'messages' is not a list", session_id)
        return
    for entry in messages:
        row = _decode_message(session_id, entry)
        if row is not None:
            yield row


def _decode_message(session_id: str, entry: object) -> MessageRow | None:
    """Decode one message entry, or None when it lacks the required shape."""
    if not isinstance(entry, dict):
        logger.warning("skipping a message in session %s: entry is not an object", session_id)
        return None
    message = cast(dict[str, Any], entry)
    message_id = message.get("id")
    role = message.get("role")
    timestamp_ms = message.get("ts")
    if not isinstance(message_id, str) or not message_id:
        logger.warning("skipping a message in session %s: missing message id", session_id)
        return None
    if not isinstance(role, str) or not role:
        logger.warning("skipping message %s: missing role", message_id)
        return None
    if not isinstance(timestamp_ms, int) or isinstance(timestamp_ms, bool):
        logger.warning("skipping message %s: missing timestamp", message_id)
        return None
    return MessageRow(
        message_id=message_id,
        session_id=session_id,
        time_created_ms=timestamp_ms,
        data=message,
    )
