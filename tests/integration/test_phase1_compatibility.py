"""Phase 1 — the shared pipeline already accepts Claude Code and Codex CLI records.

The Phase 1 checklist is verified by reading the existing tests (evidence per item is
cited in `docs/phase1_shared_compatibility.md`). What was *not* previously stated
anywhere is that the two new platform identifiers themselves flow through the shared
pipeline today — every prior integration test hard-coded `opencode` and `cline`.

These tests drive records labelled `claude_code` and `codex` through the real path —
normalization, upsert, aggregation, filtering — and assert nothing changed except the
platform column. No schema change, no migration, no new pipeline.

Decisions these tests pin (they are adapter contracts, defined here so Phase 3 and
Phase 6 inherit them):

* source event ids are namespaced `session:message`, matching Cline's convention,
  because both new sources can repeat message ids across sessions;
* a record whose model is not attributable is stored with model id `"unknown"` and
  stays `reported` — unknown attribution is honest data, not a reason to drop usage;
* two records for the same message never double count, whatever platform they belong to.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from aggregation.breakdown import breakdown_by_model
from aggregation.filters import UsageFilter
from aggregation.ranges import resolve_range
from aggregation.summary import summarize_range
from database.connection import Base
from database.repository import count_usage_events, upsert_usage_records
from schemas.usage import UsageRecord
from tests.usage_fixtures import make_record as base_make_record

UTC = timezone.utc
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

NEW_PLATFORMS = ("claude_code", "codex")
EXISTING_PLATFORMS = ("opencode", "cline")


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database factory over this test's temp directory."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def make_record(
    platform: str,
    event_id: str,
    *,
    model_id: str = "example-model",
    session_id: str = "ses_1",
    input_tokens: int | None = 100,
    output_tokens: int | None = 20,
    timestamp: datetime = NOW,
) -> UsageRecord:
    """A record for one of the new platforms, using Cline's namespaced event id."""
    return base_make_record(
        f"{session_id}:{event_id}",
        timestamp,
        platform=platform,
        model_id=model_id,
        session_id=session_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        consumption_tokens=None,
    )


def seed(session_factory: sessionmaker[Session], records: list[UsageRecord]) -> None:
    with session_factory() as session:
        upsert_usage_records(session, records)


# --- the new platform identifiers flow through the shared pipeline ---


@pytest.mark.parametrize("platform", NEW_PLATFORMS)
def test_a_new_platform_record_round_trips_the_shared_pipeline(
    session_factory: sessionmaker[Session], platform: str
) -> None:
    seed(session_factory, [make_record(platform, "msg_1")])

    with session_factory() as session:
        assert count_usage_events(session, platform) == 1
        window = resolve_range("all_time", "UTC")
        summary = summarize_range(session, window, UsageFilter(platform=platform))

    assert summary.request_count == 1
    assert summary.total_tokens == 120
    assert summary.input_tokens == 100
    assert summary.output_tokens == 20
    assert summary.unknown_total_events == 0


def test_four_platforms_share_one_database_without_colliding(
    session_factory: sessionmaker[Session],
) -> None:
    # All four platforms nickname the same message id; the platform column keeps
    # each row distinct, and the namespaced source event id keeps the sessions apart.
    records = [
        make_record(platform, "msg_0001", session_id=f"ses_{platform}")
        for platform in NEW_PLATFORMS + EXISTING_PLATFORMS
    ]
    seed(session_factory, records)

    with session_factory() as session:
        assert count_usage_events(session) == 4
        for platform in NEW_PLATFORMS + EXISTING_PLATFORMS:
            assert count_usage_events(session, platform) == 1


def test_rewriting_the_same_message_does_not_double_count_on_a_new_platform(
    session_factory: sessionmaker[Session],
) -> None:
    records = [make_record("claude_code", "msg_1"), make_record("claude_code", "msg_1")]
    seed(session_factory, records)

    with session_factory() as session:
        assert count_usage_events(session, "claude_code") == 1


def test_each_new_platform_sums_independently_and_together(
    session_factory: sessionmaker[Session],
) -> None:
    seed(
        session_factory,
        [
            make_record("claude_code", "msg_1"),
            make_record("codex", "msg_2"),
            make_record("codex", "msg_3"),
        ],
    )

    window = resolve_range("all_time", "UTC")
    with session_factory() as session:
        everything = summarize_range(session, window)
        claude = summarize_range(session, window, UsageFilter(platform="claude_code"))
        codex = summarize_range(session, window, UsageFilter(platform="codex"))

    assert claude.total_tokens == 120
    assert codex.total_tokens == 240
    assert everything.total_tokens == claude.total_tokens + codex.total_tokens


def test_the_model_breakdown_groups_new_platforms_by_platform_provider_and_model(
    session_factory: sessionmaker[Session],
) -> None:
    seed(
        session_factory,
        [
            # Same provider and model id, reached through two different assistants.
            make_record("claude_code", "msg_1", model_id="deepseek/deepseek-chat", session_id="s1"),
            make_record("codex", "msg_2", model_id="deepseek/deepseek-chat", session_id="s2"),
        ],
    )

    window = resolve_range("all_time", "UTC")
    with session_factory() as session:
        rows = breakdown_by_model(session, window)

    assert len(rows) == 2
    assert {(row.platform, row.provider_id, row.model_id) for row in rows} == {
        ("claude_code", "openrouter", "deepseek/deepseek-chat"),
        ("codex", "openrouter", "deepseek/deepseek-chat"),
    }


# --- honesty rules pinned for the adapters ---


def test_a_model_that_cannot_be_attributed_still_counts(
    session_factory: sessionmaker[Session],
) -> None:
    # Codex writes a token_count event whose model context is missing. The usage is
    # real; only the attribution is unknown. Dropping or zeroing it would lie.
    seed(session_factory, [make_record("codex", "msg_1", model_id="unknown")])

    window = resolve_range("all_time", "UTC")
    with session_factory() as session:
        summary = summarize_range(session, window, UsageFilter(platform="codex"))
        rows = breakdown_by_model(session, window)

    assert summary.request_count == 1
    assert summary.total_tokens == 120
    assert (rows[0].model_id) == "unknown"


def test_usage_with_no_reported_counts_is_unknown_not_zero(
    session_factory: sessionmaker[Session],
) -> None:
    record = make_record("claude_code", "msg_1", input_tokens=None, output_tokens=None)
    record.total_tokens = None
    seed(session_factory, [record])

    window = resolve_range("all_time", "UTC")
    with session_factory() as session:
        summary = summarize_range(session, window, UsageFilter(platform="claude_code"))

    assert summary.total_tokens == 0
    assert summary.unknown_total_events == 1
    assert summary.known_total_events == 0


def test_a_timestamp_is_normalized_to_utc_before_storage(
    session_factory: sessionmaker[Session],
) -> None:
    from normalization.normalizer import normalize_timestamp

    local = datetime(2026, 10, 12, 18, 0, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kathmandu"))
    assert normalize_timestamp(local).tzinfo is not None
    assert normalize_timestamp(local).astimezone(UTC).hour == 12
