"""Aggregation part 3: timelines and error paths."""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aggregation import (
    all_time_window,
    bucket_timeline,
    custom_window,
    summarize_range,
)
from database.connection import Base
from database.repository import upsert_usage_records
from errors.exceptions import InvalidGranularityError, InvalidTimeRangeError
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


def test_daily_timeline_buckets_each_day(session: Session) -> None:
    seed_october(session)
    window = custom_window(
        datetime(2026, 10, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 10, 12, 0, 0, tzinfo=UTC),
    )

    buckets = bucket_timeline(session, window, "day")

    assert [bucket.bucket_label for bucket in buckets] == ["2026-10-10", "2026-10-11"]
    assert buckets[0].request_count == 1
    assert buckets[0].total_tokens == 120
    assert buckets[1].request_count == 2
    assert buckets[1].total_tokens == 250


def test_timeline_buckets_sum_to_the_window_summary(session: Session) -> None:
    seed_october(session)
    window = custom_window(
        datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
    )

    summary = summarize_range(session, window)
    buckets = bucket_timeline(session, window, "day")

    assert sum(bucket.request_count for bucket in buckets) == summary.request_count
    assert sum(bucket.total_tokens for bucket in buckets) == summary.total_tokens


def test_monthly_and_yearly_timelines(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            make_record("msg_sep", datetime(2026, 9, 15, 12, 0, tzinfo=UTC)),
            make_record("msg_oct", datetime(2026, 10, 15, 12, 0, tzinfo=UTC)),
            make_record("msg_last_year", datetime(2025, 6, 15, 12, 0, tzinfo=UTC)),
        ],
    )
    window = custom_window(
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        datetime(2027, 1, 1, 0, 0, tzinfo=UTC),
    )

    months = bucket_timeline(session, window, "month")
    populated = [bucket for bucket in months if bucket.request_count > 0]
    assert [bucket.bucket_label for bucket in populated] == [
        "2025-06",
        "2026-09",
        "2026-10",
    ]

    years = bucket_timeline(session, window, "year")
    by_label = {bucket.bucket_label: bucket for bucket in years}
    assert by_label["2025"].request_count == 1
    assert by_label["2026"].request_count == 2


def test_timeline_rejects_bad_granularity(session: Session) -> None:
    window = custom_window(
        datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 10, 2, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(InvalidGranularityError):
        bucket_timeline(session, window, "hour")


def test_timeline_needs_a_bounded_window(session: Session) -> None:
    with pytest.raises(InvalidTimeRangeError):
        bucket_timeline(session, all_time_window(), "day")
