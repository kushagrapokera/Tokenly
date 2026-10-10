"""Fixtures that build a stand-in OpenCode database for boundary tests.

The schema and JSON shapes here are copied from the Phase 1 storage analysis and are
asserted against the real database by `test_learning_tests.py`. If OpenCode changes its
layout, those learning tests fail and this fixture is what needs updating.
"""

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

CREATE_SESSION_TABLE = "CREATE TABLE session (id TEXT PRIMARY KEY, time_created INTEGER NOT NULL)"
CREATE_MESSAGE_TABLE = (
    "CREATE TABLE message ("
    "id TEXT PRIMARY KEY, session_id TEXT NOT NULL, "
    "time_created INTEGER NOT NULL, data TEXT NOT NULL)"
)


@dataclass
class OpenCodeDatabaseBuilder:
    """Writes an OpenCode-shaped SQLite file and populates it with messages."""

    path: Path
    _message_count: int = field(default=0)

    def __post_init__(self) -> None:
        self._create_schema()

    def _create_schema(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(CREATE_SESSION_TABLE)
            connection.execute(CREATE_MESSAGE_TABLE)
            connection.execute("INSERT INTO session (id, time_created) VALUES ('ses_0001', 0)")

    def add_message(
        self,
        data: dict[str, object],
        *,
        message_id: str | None = None,
        session_id: str = "ses_0001",
        time_created_ms: int = 0,
        raw_data: str | None = None,
    ) -> str:
        """Insert one message row and return its id."""
        self._message_count += 1
        assigned_id = message_id or f"msg_{self._message_count:04d}"
        payload = raw_data if raw_data is not None else json.dumps(data)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO message (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
                (assigned_id, session_id, time_created_ms, payload),
            )
        return assigned_id

    def update_message(
        self,
        message_id: str,
        data: dict[str, object],
        *,
        time_created_ms: int | None = None,
    ) -> None:
        """Overwrite an existing message row, as OpenCode does when a call completes."""
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE message SET data = ?, time_created = COALESCE(?, time_created) "
                "WHERE id = ?",
                (json.dumps(data), time_created_ms, message_id),
            )

    def add_assistant_message(
        self,
        message_overrides: dict[str, object] | None = None,
        *,
        message_id: str | None = None,
        session_id: str = "ses_0001",
        time_created_ms: int = 1_700_000_000_000,
    ) -> str:
        """Insert a complete, well-formed assistant message; override any JSON field."""
        message: dict[str, object] = {
            "role": "assistant",
            "providerID": "opencode",
            "modelID": "space-bunny-free",
            "tokens": {
                "input": 100,
                "output": 20,
                "reasoning": 0,
                "cache": {"read": 0, "write": 0},
            },
            "time": {"created": 1_700_000_000_000, "completed": 1_700_000_001_000},
            "finish": "stop",
        }
        message.update(message_overrides or {})
        return self.add_message(
            message,
            message_id=message_id,
            session_id=session_id,
            time_created_ms=time_created_ms,
        )


@pytest.fixture
def opencode_db(tmp_path: Path) -> Iterator[OpenCodeDatabaseBuilder]:
    """An empty but schema-correct OpenCode database builder."""
    builder = OpenCodeDatabaseBuilder(path=tmp_path / "opencode.db")
    yield builder
