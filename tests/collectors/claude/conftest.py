"""Fixtures that build a stand-in Claude Code projects directory for tests.

The JSONL line shapes here are copied from the Phase 2 storage analysis
(`docs/claude_storage_analysis.md`) and are asserted against the real store
by `test_learning_tests.py`. If Claude Code changes its layout, those
learning tests fail and this fixture is what needs updating.

The builder reproduces the repetition the live store exhibits: one model
request (`message.id`) written to several lines (one per streamed content
block), each carrying identical usage. Tests that assert collapse behavior
therefore exercise the real shape, not a hand-simplified one.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

PROJECT_DIRECTORY_NAME = "-home-tester-project"

SES_DEFAULT_ID = "927dbe1f-44e6-4165-badf-1f97622e5829"


@dataclass
class ClaudeStoreBuilder:
    """Writes a Claude Code-shaped projects directory and populates it with sessions."""

    projects_dir: Path
    _message_count: int = field(default=0)

    def __post_init__(self) -> None:
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def add_session(self, session_id: str = SES_DEFAULT_ID) -> Path:
        """Create one empty session transcript; returns its path."""
        project_directory = self.projects_dir / PROJECT_DIRECTORY_NAME
        project_directory.mkdir(parents=True, exist_ok=True)
        transcript_path = project_directory / f"{session_id}.jsonl"
        if not transcript_path.is_file():
            transcript_path.write_text("", encoding="utf-8")
        return transcript_path

    def add_assistant_request(
        self,
        *,
        session_id: str = SES_DEFAULT_ID,
        message_id: str | None = None,
        model: str = "claude-sonnet-4-5",
        timestamp: str = "2026-09-22T11:52:31.580Z",
        input_tokens: int = 100,
        output_tokens: int = 20,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        thinking_tokens: int = 0,
        provider_prefix: str = "",
        usage: dict[str, Any] | None = None,
        line_count: int = 2,
        sidechain: bool = False,
        stop_reason: str = "tool_use",
    ) -> str:
        """Append one model request as `line_count` identical repeated lines."""
        self._message_count += 1
        assigned_id = message_id or f"{self._message_count:08x}-24ac-4fb7-9a44-58dcd7ee8ea2"
        full_model = f"{provider_prefix}{model}" if provider_prefix else model
        usage_payload = (
            usage
            if usage is not None
            else _usage_payload(
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cache_write_tokens,
                thinking_tokens,
            )
        )
        lines = [
            _assistant_line(
                assigned_id,
                full_model,
                usage_payload,
                timestamp,
                session_id,
                api_block_index=index,
                sidechain=sidechain,
                stop_reason=stop_reason,
            )
            for index in range(line_count)
        ]
        transcript_path = self.add_session(session_id)
        existing = transcript_path.read_text(encoding="utf-8")
        transcript_path.write_text(
            existing + "".join(line + "\n" for line in lines), encoding="utf-8"
        )
        return assigned_id

    def add_user_line(
        self,
        *,
        session_id: str = SES_DEFAULT_ID,
        timestamp: str = "2026-09-22T11:52:31.000Z",
    ) -> None:
        """Append a user line (never collected) to one session."""
        line = {
            "parentUuid": None,
            "isSidechain": False,
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]},
            "uuid": "3f1c4a00-0000-0000-0000-000000000001",
            "timestamp": timestamp,
            "sessionId": session_id,
        }
        transcript_path = self.add_session(session_id)
        transcript_path.write_text(
            transcript_path.read_text(encoding="utf-8") + json.dumps(line) + "\n",
            encoding="utf-8",
        )

    def write_cost_state(
        self,
        *,
        session_id: str = SES_DEFAULT_ID,
        input_tokens: int = 100,
        output_tokens: int = 20,
    ) -> None:
        """Append a final `cost-state` line, as Claude Code does on session flush.

        Its `modelUsage` totals duplicate the per-request sums, so a collector
        that ingests it as well would double every figure. The fixture exists
        so a test can prove it is ignored rather than merely absent.
        """
        line = {
            "type": "cost-state",
            "sessionId": session_id,
            "totalCostUSD": 0.1,
            "totalAPIDuration": 1234,
            "modelUsage": {
                "claude-sonnet-4-5": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "thinkingTokens": 0,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                }
            },
        }
        transcript_path = self.add_session(session_id)
        transcript_path.write_text(
            transcript_path.read_text(encoding="utf-8") + json.dumps(line) + "\n",
            encoding="utf-8",
        )

    def append_corrupt_line(self, *, session_id: str = SES_DEFAULT_ID) -> None:
        """Append one non-JSON line to prove a corrupt line is skipped, not fatal."""
        transcript_path = self.add_session(session_id)
        transcript_path.write_text(
            transcript_path.read_text(encoding="utf-8") + "{not valid json\n",
            encoding="utf-8",
        )


def _usage_payload(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    thinking_tokens: int,
) -> dict[str, Any]:
    """A usage object exactly as the live store writes it."""
    return {
        "input_tokens": input_tokens,
        "cache_creation_input_tokens": cache_write_tokens,
        "cache_read_input_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
        "output_tokens_details": {"thinking_tokens": thinking_tokens},
        "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        "service_tier": "standard",
        "cache_creation": {
            "ephemeral_1h_input_tokens": 0,
            "ephemeral_5m_input_tokens": cache_write_tokens,
        },
        "speed": "standard",
    }


def _assistant_line(
    message_id: str,
    model: str,
    usage: dict[str, Any],
    timestamp: str,
    session_id: str,
    *,
    api_block_index: int,
    sidechain: bool,
    stop_reason: str,
) -> str:
    """One assistant JSONL line, matching the live store's keyset."""
    return json.dumps(
        {
            "parentUuid": "00000000-0000-0000-0000-000000000000",
            "isSidechain": sidechain,
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": "done"}],
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": usage,
            },
            "apiBlockIndex": api_block_index,
            "type": "assistant",
            "uuid": f"{message_id[:8]}-aaaa-4bbb-8ccc-{api_block_index:012d}",
            "timestamp": timestamp,
            "effort": "max",
            "perTurnEffort": None,
            "session_id": session_id,
            "userType": "external",
            "entrypoint": "cli",
            "sessionId": session_id,
            "version": "2.1.282",
        }
    )


@pytest.fixture
def claude_store(tmp_path: Path) -> Iterator[ClaudeStoreBuilder]:
    """An empty but layout-correct Claude Code projects directory builder."""
    yield ClaudeStoreBuilder(projects_dir=tmp_path / "projects")
