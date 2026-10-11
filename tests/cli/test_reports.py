"""Tests for the CLI's pure report layer, against a seeded temporary database."""

from collections.abc import Iterator
from datetime import datetime, timezone
from itertools import count

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cli import reports
from database.connection import Base
from database.models import UsageEvent

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
_SEQUENCE = count(1)


def _add(session: Session, *, platform: str, provider: str, model: str, total: int) -> None:
    sequence = next(_SEQUENCE)
    session.add(
        UsageEvent(
            platform=platform,
            provider_id=provider,
            model_id=model,
            session_id="ses_1",
            message_id=f"m{sequence}",
            source_event_id=f"ses_1:{sequence}",
            timestamp=NOW,
            input_tokens=total - 1,
            output_tokens=1,
            total_tokens=total,
            consumption_tokens=total,
            reasoning_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            usage_status="reported",
        )
    )


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        _add(db, platform="codex", provider="deepseek", model="deepseek-flash", total=120)
        _add(db, platform="codex", provider="deepseek", model="deepseek-flash", total=120)
        _add(db, platform="codex", provider="deepseek", model="deepseek-reasoner", total=30)
        _add(db, platform="opencode", provider="openai", model="gpt-4o", total=50)
        db.commit()
        yield db


def test_available_providers_are_sorted_by_request_count(session: Session) -> None:
    assert reports.available_providers(session) == [("deepseek", 3), ("openai", 1)]


def test_available_models_sum_across_platforms_and_sort(session: Session) -> None:
    assert reports.available_models(session) == [
        ("deepseek-flash", 2),
        ("deepseek-reasoner", 1),
        ("gpt-4o", 1),
    ]


def test_model_report_all_time_totals_match_the_seed(session: Session) -> None:
    rows = reports.model_report(session, "deepseek-flash")
    all_time_label, all_time = rows[0]
    assert all_time_label == "All time"
    assert all_time.request_count == 2
    assert all_time.total_tokens == 240


def test_model_report_covers_every_window(session: Session) -> None:
    labels = [label for label, _ in reports.model_report(session, "deepseek-flash")]
    assert labels == ["All time", "Today", "Last 7 days", "This month", "Last month"]


def test_provider_report_splits_by_model(session: Session) -> None:
    rows = reports.provider_report(session, "deepseek")
    all_time_label, model_rows = rows[0]
    assert all_time_label == "All time"
    totals = {row.model_id: row.total_tokens for row in model_rows}
    assert totals == {"deepseek-flash": 240, "deepseek-reasoner": 30}


def test_provider_report_excludes_other_providers(session: Session) -> None:
    _label, model_rows = reports.provider_report(session, "deepseek")[0]
    assert all(row.provider_id == "deepseek" for row in model_rows)
    assert "gpt-4o" not in {row.model_id for row in model_rows}


def test_reports_for_an_unknown_model_are_empty_not_an_error(session: Session) -> None:
    rows = reports.model_report(session, "does-not-exist")
    assert all(summary.request_count == 0 for _label, summary in rows)
