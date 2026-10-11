"""Fixtures that build a stand-in Codex CLI home directory for tests.

The rollout JSONL line shapes here are copied from the Phase 6 storage analysis
(`docs/codex_storage_analysis.md`) and are asserted against the real store by
`test_learning_tests.py`. If Codex CLI changes its layout, those learning tests
fail and this fixture is what needs updating.

The builder reproduces the traps the live store exhibits: every usage call is
written once as `token_usage_record` and echoed once more as an `event_msg`
`token_count` line (which overcounts on aborted turns), while
`turn_token_usage` / `thread_token_usage` are cumulative rollups of the per-call
`usage`. Tests assert both are ignored rather than merely absent.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

SES_DEFAULT_ID = "01a0c92d-d997-7c82-8c58-5a5312cc8008"
TURN_DEFAULT_ID = "01a0c92d-f015-7da1-9752-b688d532e5e7"
RESPONSE_DEFAULT_ID = "f2f7a3a0-8b6f-47de-bec8-b4b574e63f12"
MODEL_DEFAULT = "deepseek-flash"
PROVIDER_DEFAULT = "deepseek"
CLI_VERSION_DEFAULT = "0.155.1"
TIMESTAMP_DEFAULT = "2026-09-22T12:53:47.767Z"

# The six top-level line types the live store writes.
LINE_TYPES = (
    "session_meta",
    "event_msg",
    "response_item",
    "world_state",
    "turn_context",
    "token_usage_record",
)

# The six fields of Codex's per-call usage object.
USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


@dataclass
class CodexStoreBuilder:
    """Writes a Codex-shaped `$CODEX_HOME` and populates it with rollout files."""

    codex_home: Path
    _ordinals: dict[Path, int] = field(default_factory=dict)
    _response_count: int = 0
    _turn_totals: dict[str, dict[str, int]] = field(default_factory=dict)
    _thread_totals: dict[str, dict[str, int]] = field(default_factory=dict)
    _turns_with_context: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)

    @property
    def sessions_dir(self) -> Path:
        return self.codex_home / "sessions"

    # --- file scaffolding ---

    def rollout_path(
        self,
        session_id: str = SES_DEFAULT_ID,
        date_parts: tuple[str, str, str] = ("2026", "09", "22"),
    ) -> Path:
        directory = self.sessions_dir.joinpath(*date_parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"rollout-2026-09-22T12-53-46-{session_id}.jsonl"

    def _append(
        self,
        path: Path,
        line_type: str,
        payload: dict[str, Any],
        timestamp: str = TIMESTAMP_DEFAULT,
    ) -> None:
        ordinal = self._ordinals.get(path, 0)
        self._ordinals[path] = ordinal + 1
        envelope = {
            "timestamp": timestamp,
            "ordinal": ordinal,
            "type": line_type,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope) + "\n")

    # --- line writers ---

    def start_session(
        self,
        *,
        session_id: str = SES_DEFAULT_ID,
        model_provider: str | None = PROVIDER_DEFAULT,
        cli_version: str = CLI_VERSION_DEFAULT,
        timestamp: str = TIMESTAMP_DEFAULT,
    ) -> Path:
        """Create the rollout file with its `session_meta` header; returns the path.

        Pass `model_provider=None` to omit the field entirely, reproducing a session
        whose provider must be inferred from a model-string gateway prefix instead.
        """
        path = self.rollout_path(session_id)
        if not path.exists():
            payload: dict[str, Any] = {
                "session_id": session_id,
                "id": session_id,
                "timestamp": timestamp,
                "cwd": "/home/tester",
                "originator": "codex-tui",
                "cli_version": cli_version,
                "source": "cli",
                "thread_source": "user",
            }
            if model_provider is not None:
                payload["model_provider"] = model_provider
            self._append(path, "session_meta", payload, timestamp)
        return path

    def add_turn_context(
        self,
        *,
        turn_id: str = TURN_DEFAULT_ID,
        model: str = MODEL_DEFAULT,
        session_id: str = SES_DEFAULT_ID,
        timestamp: str = TIMESTAMP_DEFAULT,
    ) -> None:
        """Append the `turn_context` line that supplies the model for `turn_id`."""
        path = self.start_session(session_id=session_id)
        self._append(
            path,
            "turn_context",
            {"turn_id": turn_id, "root_turn_id": turn_id, "model": model},
            timestamp,
        )
        self._turns_with_context.add(turn_id)

    def add_usage_call(
        self,
        *,
        session_id: str = SES_DEFAULT_ID,
        turn_id: str = TURN_DEFAULT_ID,
        response_id: str | None = None,
        timestamp: str = TIMESTAMP_DEFAULT,
        input_tokens: int = 100,
        output_tokens: int = 20,
        cached_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
        reasoning_output_tokens: int = 0,
        write_turn_context: bool = True,
    ) -> str:
        """Append one per-call `token_usage_record`, accumulating the turn/thread rollups."""
        if write_turn_context and turn_id not in self._turns_with_context:
            self.add_turn_context(turn_id=turn_id, session_id=session_id, timestamp=timestamp)
        self._response_count += 1
        assigned = response_id or f"resp-{self._response_count:04d}"

        usage = {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "cache_write_input_tokens": cache_write_input_tokens,
            "output_tokens": output_tokens,
            "reasoning_output_tokens": reasoning_output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
        turn_totals = self._accumulate(self._turn_totals, turn_id, usage)
        thread_totals = self._accumulate(self._thread_totals, session_id, usage)

        path = self.start_session(session_id=session_id)
        self._append(
            path,
            "token_usage_record",
            {
                "thread_id": session_id,
                "turn_id": turn_id,
                "session_id": session_id,
                "root_turn_id": turn_id,
                "response_id": assigned,
                "usage": usage,
                "turn_token_usage": dict(turn_totals),
                "thread_token_usage": dict(thread_totals),
            },
            timestamp,
        )
        return assigned

    def add_token_count_event(
        self,
        *,
        session_id: str = SES_DEFAULT_ID,
        turn_id: str = TURN_DEFAULT_ID,
        input_tokens: int = 100,
        output_tokens: int = 20,
        timestamp: str = TIMESTAMP_DEFAULT,
    ) -> None:
        """Append the `event_msg`/`token_count` line that echoes the same totals.

        Codex writes it alongside every `token_usage_record` and it double-emits on
        aborted turns, so a collector that reads it as well would overcount. It is
        never a usage source — only ever something to prove is ignored.
        """
        info = {
            "total_token_usage": {
                "input_tokens": input_tokens,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": output_tokens,
                "reasoning_output_tokens": 0,
                "total_tokens": input_tokens + output_tokens,
            },
            "model_context_window": 258400,
        }
        path = self.start_session(session_id=session_id)
        self._append(
            path,
            "event_msg",
            {"type": "token_count", "info": info, "turn_id": turn_id},
            timestamp,
        )

    def add_usageless_call(
        self,
        *,
        session_id: str = SES_DEFAULT_ID,
        turn_id: str = "turn-nousage",
        response_id: str = "resp-nousage",
        timestamp: str = TIMESTAMP_DEFAULT,
    ) -> None:
        """Append a `token_usage_record` with no `usage` object at all.

        A real session flush can land a record before its usage is filled in; the
        extractor must store it as `unavailable` (unknown), never as zero.
        """
        path = self.start_session(session_id=session_id)
        self._append(
            path,
            "token_usage_record",
            {
                "thread_id": session_id,
                "turn_id": turn_id,
                "session_id": session_id,
                "root_turn_id": turn_id,
                "response_id": response_id,
            },
            timestamp,
        )

    def append_corrupt_line(self, *, session_id: str = SES_DEFAULT_ID) -> None:
        """Append one non-JSON line to prove a corrupt line is skipped, not fatal."""
        path = self.start_session(session_id=session_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("{not valid json\n")

    # --- internals ---

    @staticmethod
    def _accumulate(
        totals: dict[str, dict[str, int]], key: str, usage: dict[str, int]
    ) -> dict[str, int]:
        running = totals.setdefault(key, {name: 0 for name in USAGE_FIELDS})
        for name in USAGE_FIELDS:
            running[name] += usage[name]
        return running


@pytest.fixture
def codex_store(tmp_path: Path) -> Iterator[CodexStoreBuilder]:
    """A stand-in Codex home directory in this test's temp directory."""
    yield CodexStoreBuilder(codex_home=tmp_path / "codex")
