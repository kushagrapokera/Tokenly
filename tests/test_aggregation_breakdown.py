"""Aggregation part 2: coverage, filters, breakdowns."""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aggregation import (
    UsageFilter,
    all_time_window,
    breakdown_by_model,
    summarize_range,
)
from database.connection import Base
from database.repository import upsert_usage_records
from tests.test_aggregation import make_record, seed_october

UTC = timezone.utc


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    """A session against a fresh SQLite database with the schema created."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as open_session:
        yield open_session
    engine.dispose()


def test_unknown_records_excluded_from_sums_but_counted(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            make_record(
                "msg_unknown",
                datetime(2026, 10, 11, 10, 0, tzinfo=UTC),
                input_tokens=None,
                output_tokens=None,
                usage_status="unavailable",
            ),
        ],
    )

    summary = summarize_range(session, all_time_window())

    assert summary.request_count == 1
    assert summary.total_tokens == 0
    assert summary.unknown_total_events == 1
    assert summary.known_total_events == 0


def test_summary_respects_provider_and_model_filters(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            make_record("msg_a", datetime(2026, 10, 11, 9, 0, tzinfo=UTC)),
            make_record(
                "msg_b",
                datetime(2026, 10, 11, 9, 30, tzinfo=UTC),
                provider_id="anthropic",
                model_id="other-model",
                input_tokens=1000,
                output_tokens=500,
            ),
        ],
    )

    filtered = summarize_range(session, all_time_window(), UsageFilter(provider_id="anthropic"))
    assert filtered.request_count == 1
    assert filtered.total_tokens == 1500

    by_model = summarize_range(session, all_time_window(), UsageFilter(model_id="example-model"))
    assert by_model.request_count == 1
    assert by_model.total_tokens == 120


def test_breakdown_keeps_same_named_models_apart(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            make_record(
                "msg_openrouter",
                datetime(2026, 10, 11, 9, 0, tzinfo=UTC),
                provider_id="openrouter",
                model_id="shared-name",
            ),
            make_record(
                "msg_anthropic",
                datetime(2026, 10, 11, 10, 0, tzinfo=UTC),
                provider_id="anthropic",
                model_id="shared-name",
                input_tokens=1000,
                output_tokens=500,
            ),
        ],
    )

    rows = breakdown_by_model(session, all_time_window())

    assert len(rows) == 2
    assert rows[0].provider_id == "anthropic"
    assert rows[0].total_tokens == 1500
    assert rows[1].provider_id == "openrouter"
    assert rows[1].total_tokens == 120


def test_breakdown_sums_to_the_window_summary(session: Session) -> None:
    seed_october(session)
    window = all_time_window()

    summary = summarize_range(session, window)
    rows = breakdown_by_model(session, window)

    assert sum(row.request_count for row in rows) == summary.request_count
    assert sum(row.total_tokens for row in rows) == summary.total_tokens
    assert sum(row.unknown_total_events for row in rows) == summary.unknown_total_events


def test_breakdown_respects_filters(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            make_record("msg_a", datetime(2026, 10, 11, 9, 0, tzinfo=UTC)),
            make_record(
                "msg_b",
                datetime(2026, 10, 11, 10, 0, tzinfo=UTC),
                provider_id="anthropic",
                model_id="other-model",
            ),
        ],
    )

    rows = breakdown_by_model(session, all_time_window(), UsageFilter(platform="opencode"))
    assert len(rows) == 2
    rows = breakdown_by_model(session, all_time_window(), UsageFilter(provider_id="anthropic"))
    assert len(rows) == 1
    assert rows[0].model_id == "other-model"
