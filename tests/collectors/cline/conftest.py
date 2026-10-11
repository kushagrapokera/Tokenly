"""Fixtures that build a stand-in Cline data directory for boundary tests.

The session-index schema and message JSON shapes here are copied from the
Phase 1 storage analysis (`docs/cline_storage_analysis.md`) and are asserted
against the real store by `test_learning_tests.py`. If Cline changes its
layout, those learning tests fail and this fixture is what needs updating.
"""

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

CREATE_SESSIONS_TABLE = (
    "CREATE TABLE sessions ("
    "session_id TEXT PRIMARY KEY, messages_path TEXT NOT NULL, metadata_json TEXT NOT NULL)"
)


@dataclass
class ClineStoreBuilder:
    """Writes a Cline-shaped data directory and populates it with sessions."""

    data_dir: Path
    _message_count: int = field(default=0)

    def __post_init__(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "db").mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.index_path) as connection:
            connection.execute(CREATE_SESSIONS_TABLE)

    @property
    def sessions_dir(self) -> Path:
        """The directory holding per-session message files."""
        return self.data_dir / "sessions"

    @property
    def index_path(self) -> Path:
        """The session index database path."""
        return self.data_dir / "db" / "sessions.db"

    def add_session(
        self,
        session_id: str = "ses_0001",
        *,
        indexed: bool = True,
    ) -> Path:
        """Create one session directory (and optionally its index row)."""
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        messages_path = session_dir / f"{session_id}.messages.json"
        if not messages_path.is_file():
            messages_path.write_text(
                json.dumps({"version": 1, "sessionId": session_id, "messages": []}),
                encoding="utf-8",
            )
        if indexed:
            with sqlite3.connect(self.index_path) as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO sessions (session_id, messages_path, metadata_json)"
                    " VALUES (?, ?, ?)",
                    (session_id, str(messages_path), "{}"),
                )
        return session_dir

    def add_assistant_message(
        self,
        message_overrides: dict[str, Any] | None = None,
        *,
        session_id: str = "ses_0001",
        message_id: str | None = None,
        time_created_ms: int = 1_790_495_317_187,
        indexed: bool = True,
    ) -> str:
        """Append a complete, well-formed assistant message to one session file."""
        self._message_count += 1
        assigned_id = message_id or f"msg_{self._message_count:04d}"
        message: dict[str, Any] = {
            "id": assigned_id,
            "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
            "ts": time_created_ms,
            "modelInfo": {"id": "cline-free/gemini-3.8-flash", "provider": "cline"},
            "metrics": {
                "inputTokens": 100,
                "outputTokens": 20,
                "cacheReadTokens": 5,
                "cacheWriteTokens": 0,
            },
        }
        if message_overrides:
            message.update(message_overrides)
        session_dir = self.add_session(session_id, indexed=indexed)
        messages_path = session_dir / f"{session_id}.messages.json"
        payload = json.loads(messages_path.read_text(encoding="utf-8"))
        payload["messages"].append(message)
        messages_path.write_text(json.dumps(payload), encoding="utf-8")
        return assigned_id

    def add_user_message(
        self,
        session_id: str = "ses_0001",
        *,
        message_id: str = "user_0001",
        time_created_ms: int = 1_790_495_314_350,
    ) -> str:
        """Append a user message (never collected) to one session file."""
        session_dir = self.add_session(session_id)
        messages_path = session_dir / f"{session_id}.messages.json"
        payload = json.loads(messages_path.read_text(encoding="utf-8"))
        payload["messages"].append(
            {
                "id": message_id,
                "role": "user",
                "content": [{"type": "text", "text": "hello"}],
                "ts": time_created_ms,
            }
        )
        messages_path.write_text(json.dumps(payload), encoding="utf-8")
        return message_id


@pytest.fixture
def cline_store(tmp_path: Path) -> Iterator[ClineStoreBuilder]:
    """An empty but schema-correct Cline data directory builder."""
    yield ClineStoreBuilder(data_dir=tmp_path / "cline-data")
