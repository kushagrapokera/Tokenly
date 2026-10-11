"""Aggregation tests: summaries, model breakdowns, timelines.

Every test stores rows through the real `upsert_usage_records` path, so what
is asserted is what the database actually holds, not a hand-built fixture.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aggregation import (
    all_time_window,
    current_month_window,
    current_year_window,
    custom_window,
    last_7_days_window,
    previous_month_window,
    summarize_range,
    today_window,
    yesterday_window,
)
from database.connection import Base
from database.repository import upsert_usage_records
from schemas.usage import UsageRecord

UTC = timezone.utc


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    """A session against a fresh SQLite database with the schema created."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as open_session:
        yield open_session
    engine.dispose()


def make_record(
    event_id: str,
    timestamp: datetime,
    *,
    provider_id: str = "openrouter",
    model_id: str = "example-model",
    input_tokens: int | None = 100,
    output_tokens: int | None = 20,
    usage_status: str = "reported",
) -> UsageRecord:
    """One normalized record standing in for a stored model call."""
    total = None
    if input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    return UsageRecord(
        platform="opencode",
        provider_id=provider_id,
        model_id=model_id,
        session_id="ses_1",
        message_id=event_id,
        source_event_id=event_id,
        timestamp=timestamp,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total,
        reasoning_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
        consumption_tokens=total,
        usage_status=usage_status,  # type: ignore[arg-type]
        raw_usage={},
    )


def seed_october(session: Session) -> None:
    """Store three records: one yesterday, two today (one unknown)."""
    upsert_usage_records(
        session,
        [
            make_record("msg_yesterday", datetime(2026, 10, 10, 9, 0, tzinfo=UTC)),
            make_record(
                "msg_today_first",
                datetime(2026, 10, 11, 9, 0, tzinfo=UTC),
                input_tokens=200,
                output_tokens=50,
            ),
            make_record(
                "msg_today_unknown",
                datetime(2026, 10, 11, 10, 0, tzinfo=UTC),
                input_tokens=None,
                output_tokens=None,
                usage_status="unavailable",
            ),
        ],
    )


def test_today_summary_counts_only_today(session: Session) -> None:
    seed_october(session)
    now = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

    summary = summarize_range(session, today_window("UTC", now=now))

    assert summary.window_label == "today"
    assert summary.request_count == 2
    assert summary.input_tokens == 200
    assert summary.output_tokens == 50
    assert summary.total_tokens == 250
    assert summary.known_total_events == 1
    assert summary.unknown_total_events == 1


def test_yesterday_summary(session: Session) -> None:
    seed_october(session)
    now = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

    summary = summarize_range(session, yesterday_window("UTC", now=now))

    assert summary.request_count == 1
    assert summary.total_tokens == 120


def test_last_7_days_matches_sum_of_days(session: Session) -> None:
    seed_october(session)
    now = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

    week = summarize_range(session, last_7_days_window("UTC", now=now))
    today = summarize_range(session, today_window("UTC", now=now))
    yesterday = summarize_range(session, yesterday_window("UTC", now=now))

    assert week.request_count == today.request_count + yesterday.request_count
    assert week.total_tokens == today.total_tokens + yesterday.total_tokens
    assert week.known_total_events == 2
    assert week.unknown_total_events == 1


def test_month_and_year_windows_agree(session: Session) -> None:
    seed_october(session)
    now = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

    month = summarize_range(session, current_month_window("UTC", now=now))
    year = summarize_range(session, current_year_window("UTC", now=now))
    all_time = summarize_range(session, all_time_window())

    assert month.request_count == year.request_count == all_time.request_count == 3
    assert month.total_tokens == 120 + 250


def test_previous_month_is_empty(session: Session) -> None:
    seed_october(session)
    now = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

    summary = summarize_range(session, previous_month_window("UTC", now=now))

    assert summary.request_count == 0
    assert summary.total_tokens == 0
    assert summary.unknown_total_events == 0


def test_custom_window_is_half_open(session: Session) -> None:
    """An event exactly at the end belongs to the next window, not this one."""
    upsert_usage_records(
        session,
        [
            make_record("msg_start", datetime(2026, 10, 1, 0, 0, tzinfo=UTC)),
            make_record("msg_end", datetime(2026, 10, 2, 0, 0, tzinfo=UTC)),
        ],
    )
    window = custom_window(
        datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 10, 2, 0, 0, tzinfo=UTC),
    )

    summary = summarize_range(session, window)

    assert summary.request_count == 1
    assert summary.total_tokens == 120
