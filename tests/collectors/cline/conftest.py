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
    "session_id TEXT PRIMARY KEY, messages_path TEXT NOT NULL, metadata_json TEXT NOT NULL, "
    "is_subagent INTEGER NOT NULL DEFAULT 0, parent_session_id TEXT)"
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
        is_subagent: bool = False,
        parent_session_id: str | None = None,
    ) -> Path:
        """Create one session directory and, unless skipped, its index row.

        The subagent columns are part of Cline's real `sessions` table
        (`docs/cline_storage_analysis.md` §2). They are all zero/null in a live
        store today, so a test has to be able to write them to prove subagent
        usage would still be attributed correctly if a Cline version populates
        them.
        """
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
                    "INSERT OR IGNORE INTO sessions "
                    "(session_id, messages_path, metadata_json, is_subagent, parent_session_id)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (session_id, str(messages_path), "{}", int(is_subagent), parent_session_id),
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
        is_subagent: bool = False,
        parent_session_id: str | None = None,
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
        session_dir = self.add_session(
            session_id,
            indexed=indexed,
            is_subagent=is_subagent,
            parent_session_id=parent_session_id,
        )
        messages_path = session_dir / f"{session_id}.messages.json"
        payload = json.loads(messages_path.read_text(encoding="utf-8"))
        payload["messages"].append(message)
        messages_path.write_text(json.dumps(payload), encoding="utf-8")
        return assigned_id

    def add_error_message(
        self,
        *,
        session_id: str = "ses_0001",
        message_id: str | None = None,
        time_created_ms: int = 1_790_495_317_187,
    ) -> str:
        """Append a failed call: an assistant message Cline wrote with no metrics.

        Cline records a rate limit, a missing model, or a timeout as a display-only
        assistant message carrying `displayOnly`/`displayRole` and nothing else. It
        is a real entry in the history, so it is stored as unavailable rather than
        dropped, but it never contributes a token count.
        """
        self._message_count += 1
        assigned_id = message_id or f"error_{self._message_count:04d}"
        return self.add_assistant_message(
            {
                "metrics": None,
                "metadata": {"displayOnly": True, "displayRole": "error"},
                "content": [{"type": "text", "text": '{"error":{"code":"INFERENCE_CAP_ERROR"}}'}],
            },
            session_id=session_id,
            message_id=assigned_id,
            time_created_ms=time_created_ms,
        )

    def write_session_rollup(
        self,
        session_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
    ) -> Path:
        """Write the session envelope carrying `metadata.usage`, as Cline does.

        These totals duplicate the per-message sums exactly, so a collector that
        ingests them as well would double every figure. The fixture exists so a
        test can prove they are ignored rather than merely absent.
        """
        session_dir = self.add_session(session_id)
        envelope_path = session_dir / f"{session_id}.json"
        envelope_path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "provider": "cline",
                    "model": "cline-free/gemini-3.8-flash",
                    "status": "completed",
                    "metadata": {
                        "usage": {
                            "inputTokens": input_tokens,
                            "outputTokens": output_tokens,
                            "cacheReadTokens": cache_read_tokens,
                            "cacheWriteTokens": 0,
                            "totalCost": 0,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return envelope_path

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
