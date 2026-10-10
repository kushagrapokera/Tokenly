"""Read raw session and message rows out of an OpenCode database snapshot.

This module is the only place that knows OpenCode's SQL schema. Everything above it
works with the plain Python shapes defined here, so a schema change fails loudly in
the learning tests rather than silently skewing totals.

Schema pinned by these queries (verified against OpenCode 1.18.35):
  session(id, project_id, time_created, ...)          - one row per conversation
  message(id, session_id, time_created, data)          - one row per turn; data is JSON

`json_valid(data)` guards `json_extract`: SQLite raises "malformed JSON" on a corrupt
row, which would abort the whole scan rather than skip one bad message.
"""

import json
import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from errors.exceptions import UnsupportedStorageFormatError

logger = logging.getLogger(__name__)

ASSISTANT_ROLE = "assistant"

_SESSION_QUERY = "SELECT id, time_created FROM session ORDER BY time_created"
_MESSAGE_QUERY = (
    "SELECT id, session_id, time_created, data FROM message "
    "WHERE json_valid(data) AND json_extract(data, '$.role') = ? ORDER BY time_created"
)
_COUNT_QUERY = (
    "SELECT COUNT(*) FROM message WHERE json_valid(data) AND json_extract(data, '$.role') = ?"
)

REQUIRED_TABLES = frozenset({"session", "message"})


@dataclass(frozen=True)
class SessionRow:
    """One OpenCode conversation, as stored in the `session` table."""

    session_id: str
    time_created_ms: int


@dataclass(frozen=True)
class MessageRow:
    """One OpenCode message, with its JSON payload already decoded."""

    message_id: str
    session_id: str
    time_created_ms: int
    data: dict[str, object]


def open_snapshot(snapshot_path: Path) -> sqlite3.Connection:
    """Open a snapshot read-only and confirm it holds the tables we expect."""
    connection = sqlite3.connect(f"file:{snapshot_path}?mode=ro", uri=True)
    verify_supported_schema(connection, snapshot_path)
    return connection


def verify_supported_schema(connection: sqlite3.Connection, snapshot_path: Path) -> None:
    """Raise UnsupportedStorageFormatError unless the snapshot has OpenCode's tables."""
    present = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = REQUIRED_TABLES - present
    if missing:
        raise UnsupportedStorageFormatError(
            str(snapshot_path), f"missing table(s): {', '.join(sorted(missing))}"
        )
    logger.debug("verified snapshot schema at %s", snapshot_path)


def list_sessions(connection: sqlite3.Connection) -> list[SessionRow]:
    """Return every session, oldest first."""
    return [
        SessionRow(session_id=row[0], time_created_ms=int(row[1]))
        for row in connection.execute(_SESSION_QUERY)
    ]


def iter_assistant_messages(connection: sqlite3.Connection) -> Iterator[MessageRow]:
    """Yield every assistant message row in chronological order.

    Rows whose `data` column is not decodable JSON are logged and skipped: one bad row
    must not abort a whole history import.
    """
    for message_id, session_id, time_created, raw_data in connection.execute(
        _MESSAGE_QUERY, (ASSISTANT_ROLE,)
    ):
        try:
            data = json.loads(raw_data)
        except (json.JSONDecodeError, TypeError):
            logger.warning("skipping message %s: data column is not valid JSON", message_id)
            continue
        if not isinstance(data, dict):
            logger.warning("skipping message %s: data column is not a JSON object", message_id)
            continue
        yield MessageRow(
            message_id=message_id,
            session_id=session_id,
            time_created_ms=int(time_created),
            data=data,
        )


def count_assistant_messages(connection: sqlite3.Connection) -> int:
    """Return how many assistant messages the snapshot holds."""
    return int(connection.execute(_COUNT_QUERY, (ASSISTANT_ROLE,)).fetchone()[0])
