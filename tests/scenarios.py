"""End-to-end scenario harness: a fake OpenCode source feeding the real pipeline.

A scenario test here is not a unit test with extra steps. Each one drives the whole
path OpenCode's data actually takes — read the source database through the collector,
run the sync service, store through the repository, then aggregate with the same code
the API uses — and then asserts on what a user would see. That is the only way to catch
a break that only appears where those pieces meet, such as a checkpoint that advances
past an unfinished message.

Scenarios mutate the *source* between runs, exactly as OpenCode does in reality: a
message gaining tokens when it finishes, a retry rewriting a row, a compaction emptying
a session. Nothing reaches into Tokenly's database to set up a state.
"""

import json
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from aggregation.breakdown import ModelUsage, breakdown_by_model
from aggregation.filters import UsageFilter
from aggregation.ranges import resolve_range
from aggregation.summary import UsageSummary, summarize_range
from collectors.opencode import OpenCodeCollector
from collectors.opencode.locator import DATABASE_FILE_NAME
from config.settings import Settings
from database.connection import Base, create_database_engine, create_session_factory
from database.repository import count_usage_events
from database.state import CollectorProgress, load_progress
from sync.result import SyncResult
from sync.service import SyncService
from tests.collectors.opencode.conftest import (
    CREATE_MESSAGE_TABLE,
    CREATE_SESSION_TABLE,
)

T = TypeVar("T")

BASE_MS = 1_700_000_000_000
MINUTE_MS = 60_000


@dataclass
class StoredMessage:
    """One assistant message as OpenCode would write it.

    `completed=False` models a request still generating: OpenCode writes the row when
    generation starts and only later fills in `time.completed` and `tokens`. That is
    the state the collector must defer rather than record.
    """

    message_id: str
    session_id: str = "ses_0001"
    created_ms: int = BASE_MS
    provider_id: str = "opencode"
    model_id: str = "space-bunny-free"
    tokens: dict[str, object] | None = None
    finish: str | None = "stop"
    completed: bool = True

    def as_json(self) -> str:
        """Render the `message.data` payload OpenCode stores."""
        time_block: dict[str, object] = {"created": self.created_ms}
        if self.completed:
            time_block["completed"] = self.created_ms + 1_000

        message: dict[str, object] = {
            "role": "assistant",
            "providerID": self.provider_id,
            "modelID": self.model_id,
            "time": time_block,
        }
        if self.finish is not None:
            message["finish"] = self.finish
        if self.tokens is not None:
            message["tokens"] = self.tokens
        return json.dumps(message)


def tokens(
    input: int = 100,
    output: int = 20,
    reasoning: int = 0,
    cache_read: int = 0,
    cache_write: int = 0,
) -> dict[str, object]:
    """Build an OpenCode token payload; omit `total`, which Tokenly never trusts."""
    return {
        "input": input,
        "output": output,
        "reasoning": reasoning,
        "cache": {"read": cache_read, "write": cache_write},
    }


class ScenarioEnvironment:
    """A fake OpenCode source plus a Tokenly database, wired to the real pipeline.

    `restart()` deliberately builds a new engine, session factory, collector, and sync
    service, so nothing a test set up can survive in memory. That is what makes the
    application-restart scenario mean anything.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.source_dir = root / "opencode-source"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.source_path = self.source_dir / DATABASE_FILE_NAME
        self.tokenly_path = root / "tokenly.db"
        self.settings = Settings(
            database_path=self.tokenly_path,
            opencode_data_dir=self.source_dir,
            log_level="WARNING",
            rescan_overlap_ms=0,
        )
        self._create_source_schema()

    def _create_source_schema(self) -> None:
        with sqlite3.connect(self.source_path) as connection:
            connection.execute(CREATE_SESSION_TABLE)
            connection.execute(CREATE_MESSAGE_TABLE)

    def _session(self) -> tuple[sessionmaker[Session], Engine]:
        """Open a session factory over the Tokenly database, schema included."""
        engine = create_database_engine(self.settings.database_url)
        Base.metadata.create_all(engine)
        return create_session_factory(engine), engine

    def write_message(self, message: StoredMessage) -> None:
        """Insert a message into the source, as OpenCode does when a call starts."""
        with sqlite3.connect(self.source_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO message (id, session_id, time_created, data) "
                "VALUES (?, ?, ?, ?)",
                (
                    message.message_id,
                    message.session_id,
                    message.created_ms,
                    message.as_json(),
                ),
            )

    def delete_message(self, message_id: str) -> None:
        """Remove a message from the source, as compaction or cleanup does."""
        with sqlite3.connect(self.source_path) as connection:
            connection.execute("DELETE FROM message WHERE id = ?", (message_id,))

    def compact_session(self, session_id: str) -> None:
        """Empty an entire session from the source."""
        with sqlite3.connect(self.source_path) as connection:
            connection.execute("DELETE FROM message WHERE session_id = ?", (session_id,))

    def write(self, messages: list[StoredMessage]) -> None:
        """Insert several messages in order."""
        for message in messages:
            self.write_message(message)

    def sync(self, *, from_scratch: bool = False) -> SyncResult:
        """Run one synchronization pass through the real collector and service."""
        factory, engine = self._session()
        collector = OpenCodeCollector(self.settings)
        try:
            with factory() as session:
                return SyncService(collector).run(session, from_scratch=from_scratch)
        finally:
            engine.dispose()

    def restart(self) -> None:
        """Discard every in-memory object, leaving only the two database files."""
        self.settings = Settings(
            database_path=self.tokenly_path,
            opencode_data_dir=self.source_dir,
            log_level="WARNING",
            rescan_overlap_ms=0,
        )

    def _aggregate(self, build: Callable[[Session], T]) -> T:
        """Run one read against a throwaway session, then close everything."""
        factory, engine = self._session()
        try:
            with factory() as session:
                return build(session)
        finally:
            engine.dispose()

    def summary(self, range_name: str = "all_time", **filters: str | None) -> UsageSummary:
        """Aggregate stored usage exactly as the API does."""
        window = resolve_range(range_name, "UTC")
        usage_filter = UsageFilter(**filters) if filters else None
        return self._aggregate(lambda session: summarize_range(session, window, usage_filter))

    def models(self, range_name: str = "all_time") -> list[ModelUsage]:
        """Aggregate the per-model breakdown exactly as the API does."""
        window = resolve_range(range_name, "UTC")
        return self._aggregate(lambda session: breakdown_by_model(session, window))

    def stored_events(self) -> int:
        """Count stored usage events."""
        return self._aggregate(lambda session: count_usage_events(session))

    def progress(self) -> CollectorProgress | None:
        """Read the stored checkpoint for the collector."""
        return self._aggregate(lambda session: load_progress(session, "opencode"))


@dataclass(frozen=True)
class Totals:
    """The four token figures a summary carries, for whole-summary comparison."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    consumption_tokens: int


def totals_of(summary: UsageSummary) -> Totals:
    """Extract a summary's token figures so two summaries can be compared whole."""
    return Totals(
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        total_tokens=summary.total_tokens,
        consumption_tokens=summary.consumption_tokens,
    )


def make_scenario(tmp_path: Path) -> Iterator[ScenarioEnvironment]:
    """Yield a fresh scenario environment inside the test's temporary directory."""
    yield ScenarioEnvironment(tmp_path / "scenario")
