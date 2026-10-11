"""Both platforms through every view and metric the dashboard needs (Phase 6).

Phase 6 asks for three views — OpenCode only, Cline only, and everything
combined — over six metrics: daily, monthly, yearly, and all-time totals, model
wiseness, and the input/output split. None of that needs a Cline-specific
aggregation: the shared functions already read the same normalized rows for both
platforms, so these tests drive the existing endpoints and prove the numbers are
right rather than writing a second set of aggregation code.

The one thing that did need fixing is here: the model breakdown grouped by
provider and model only, so the same model name reached through two platforms
would have been merged into a single row.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import Settings
from database.connection import Base
from database.repository import upsert_usage_records
from main import create_app
from schemas.usage import UsageRecord, UsageStatus

UTC = timezone.utc
NOW = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


def make_record(
    platform: str,
    event_id: str,
    *,
    provider: str = "cline",
    model: str = "shared-model",
    timestamp: datetime = NOW,
    input_tokens: int | None = 100,
    output_tokens: int | None = 10,
    cache_read: int | None = 40,
) -> UsageRecord:
    """A record standing in for one stored model call."""
    if input_tokens is not None and output_tokens is not None:
        per_call = input_tokens + output_tokens
        consumption = per_call + (cache_read or 0)
        status: UsageStatus = "reported"
    else:
        # The call happened but Cline never reported what it cost.
        per_call = None
        consumption = None
        status = "unavailable"
    return UsageRecord(
        platform=platform,
        provider_id=provider,
        model_id=model,
        session_id="ses_1",
        message_id=event_id,
        source_event_id=f"ses_1:{event_id}",
        timestamp=timestamp,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=per_call,
        consumption_tokens=consumption,
        cache_read_tokens=cache_read,
        usage_status=status,
    )


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database factory for the test to store records into."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def client(tmp_path: Path, session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """An API client over a database holding both platforms' usage."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(database_path=tmp_path / "api.db", log_level="WARNING", sync_enabled=False)
    application = create_app(settings)
    factory = sessionmaker(bind=engine)
    application.state.session_factory = factory
    with factory() as session:
        upsert_usage_records(
            session,
            [
                # Cline: two models, one of them shared with OpenCode.
                make_record("cline", "c1", model="gemini-3.8-flash"),
                make_record("cline", "c2", model="muse-spark"),
                make_record("cline", "c3", model="muse-spark", timestamp=NOW - timedelta(days=40)),
                # A Cline call Cline never reported usage for.
                make_record("cline", "c4", input_tokens=None, output_tokens=None),
                # OpenCode: same model name, different provider.
                make_record("opencode", "o1", provider="opencode", model="muse-spark"),
                make_record(
                    "opencode",
                    "o2",
                    provider="opencode",
                    model="sonnet",
                    timestamp=NOW - timedelta(days=400),
                ),
            ],
        )

    with TestClient(application) as test_client:
        yield test_client
    engine.dispose()


def totals(body: dict[str, Any]) -> dict[str, int]:
    """Pull the token totals out of a response body."""
    raw = body["totals"]
    assert isinstance(raw, dict)
    return cast(dict[str, int], raw)


# --- the three required views ---


def test_the_combined_view_adds_both_platforms(client: TestClient) -> None:
    body = client.get("/api/usage/summary").json()

    # Five reported records of 110 each; Cline's unreported call contributes nothing.
    assert totals(body)["total_tokens"] == 550


def test_each_platform_can_be_viewed_on_its_own(client: TestClient) -> None:
    cline = client.get("/api/usage/summary", params={"platform": "cline"}).json()
    opencode = client.get("/api/usage/summary", params={"platform": "opencode"}).json()

    assert totals(cline)["total_tokens"] == 330
    assert totals(opencode)["total_tokens"] == 220
    assert totals(cline)["total_tokens"] + totals(opencode)["total_tokens"] == totals(
        client.get("/api/usage/summary").json()
    )["total_tokens"]


def test_a_platform_with_no_usage_reports_zeroes_rather_than_failing(client: TestClient) -> None:
    body = client.get("/api/usage/summary", params={"platform": "codex"}).json()

    assert body["filters"]["platform"] == "codex"
    assert totals(body)["total_tokens"] == 0


# --- the required metrics ---


def test_the_input_and_output_split_is_kept_per_platform(client: TestClient) -> None:
    cline = client.get("/api/usage/summary", params={"platform": "cline"}).json()

    assert totals(cline)["input_tokens"] == 300
    assert totals(cline)["output_tokens"] == 30
    assert totals(cline)["total_tokens"] == 330


def test_consumption_adds_cache_without_inflating_the_per_call_total(client: TestClient) -> None:
    body = client.get("/api/usage/summary", params={"platform": "cline"}).json()

    # Four reported calls at 110, each also reading 40 cached tokens.
    assert totals(body)["total_tokens"] == 330
    assert totals(body)["consumption_tokens"] == 450


def test_daily_usage_is_available_for_each_platform(client: TestClient) -> None:
    body = client.get(
        "/api/usage/daily",
        params={"range": "all_time", "platform": "cline", "granularity": "day"},
    ).json()

    assert body["buckets"]
    assert sum(bucket["totals"]["total_tokens"] for bucket in body["buckets"]) == 330


def test_monthly_usage_is_available_for_each_platform(client: TestClient) -> None:
    body = client.get(
        "/api/usage/monthly",
        params={"range": "all_time", "platform": "cline"},
    ).json()

    assert body["granularity"] == "month"
    assert sum(bucket["totals"]["total_tokens"] for bucket in body["buckets"]) == 330


def test_yearly_usage_separates_the_two_years_in_the_data(client: TestClient) -> None:
    # An all_time timeline deliberately falls back to the current year, so a range
    # spanning both years is asked for explicitly.
    body = client.get(
        "/api/usage/yearly",
        params={
            "range": "custom",
            "start": "2025-01-01T00:00:00Z",
            "end": "2026-12-31T23:59:59Z",
            "platform": "opencode",
        },
    ).json()

    assert [bucket["label"] for bucket in body["buckets"]] == ["2025", "2026"]
    assert [bucket["totals"]["total_tokens"] for bucket in body["buckets"]] == [110, 110]


def test_an_unbounded_timeline_falls_back_to_a_bounded_one(client: TestClient) -> None:
    # Guarding against a chart that tries to plot every year since the epoch: an
    # all-time request is narrowed to the current year, so the older record falls
    # outside the chart even though the requested range is echoed back.
    body = client.get("/api/usage/yearly", params={"range": "all_time"}).json()

    assert body["window"]["range"] == "all_time"
    assert body["window"]["start"] is not None
    assert [bucket["label"] for bucket in body["buckets"]] == [str(NOW.year)]


def test_all_time_usage_spans_every_record(client: TestClient) -> None:
    body = client.get("/api/usage/summary", params={"range": "all_time"}).json()

    assert body["window"]["range"] == "all_time"
    assert body["window"]["start"] is None


def test_usage_can_be_narrowed_to_one_model_within_one_platform(client: TestClient) -> None:
    body = client.get(
        "/api/usage/summary",
        params={"platform": "cline", "model_id": "muse-spark"},
    ).json()

    assert totals(body)["total_tokens"] == 220


# --- model-wise usage ---


def test_the_model_breakdown_keeps_the_same_model_name_on_two_platforms_apart(
    client: TestClient,
) -> None:
    # Both platforms served `muse-spark`. Grouped by provider and model alone they
    # would collapse into one row and the platform column would be unreportable.
    rows = client.get("/api/usage/models").json()["models"]
    muse_rows = [
        (row["platform"], row["provider_id"]) for row in rows if row["model_id"] == "muse-spark"
    ]

    assert sorted(muse_rows) == [("cline", "cline"), ("opencode", "opencode")]


def test_every_model_row_names_its_platform(client: TestClient) -> None:
    rows = client.get("/api/usage/models").json()["models"]

    assert {row["platform"] for row in rows} == {"cline", "opencode"}
    assert all(row["platform"] for row in rows)


def test_the_model_breakdown_reconciles_with_the_combined_summary(client: TestClient) -> None:
    rows = client.get("/api/usage/models").json()["models"]
    summary = client.get("/api/usage/summary").json()

    assert sum(row["totals"]["total_tokens"] for row in rows) == totals(summary)["total_tokens"]
    assert sum(row["request_count"] for row in rows) == summary["completeness"]["request_count"]


def test_the_breakdown_can_be_filtered_to_one_platform(client: TestClient) -> None:
    rows = client.get("/api/usage/models", params={"platform": "cline"}).json()["models"]

    assert {row["platform"] for row in rows} == {"cline"}
    assert sum(row["totals"]["total_tokens"] for row in rows) == 330


def test_the_breakdown_reports_provider_and_model_apart(client: TestClient) -> None:
    rows = client.get("/api/usage/models").json()["models"]
    identities = {(row["platform"], row["provider_id"], row["model_id"]) for row in rows}

    assert ("cline", "cline", "gemini-3.8-flash") in identities
    assert ("opencode", "opencode", "sonnet") in identities


# --- completeness, which matters most for Cline ---


def test_unreported_cline_usage_is_visible_rather_than_counted_as_zero(client: TestClient) -> None:
    body = client.get("/api/usage/summary", params={"platform": "cline"}).json()

    assert body["completeness"]["unknown_total_events"] == 1
    assert body["completeness"]["is_complete"] is False


def test_a_fully_reported_platform_is_marked_complete(client: TestClient) -> None:
    body = client.get("/api/usage/summary", params={"platform": "opencode"}).json()

    assert body["completeness"]["unknown_total_events"] == 0
    assert body["completeness"]["is_complete"] is True


def test_unknown_usage_is_reported_per_model_too(client: TestClient) -> None:
    rows = client.get("/api/usage/models", params={"platform": "cline"}).json()["models"]

    assert sum(row["unknown_total_events"] for row in rows) == 1


# --- timezone handling for a platform whose timestamps are UTC milliseconds ---


def test_buckets_follow_the_requested_timezone_not_utc(client: TestClient) -> None:
    late = make_record("cline", "c5", timestamp=NOW.replace(hour=23, minute=30))
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        upsert_usage_records(session, [late])

    utc = client.get(
        "/api/usage/daily", params={"range": "all_time", "platform": "cline"}
    ).json()
    kathmandu = client.get(
        "/api/usage/daily",
        params={"range": "all_time", "platform": "cline", "timezone": "Asia/Kathmandu"},
    ).json()

    assert utc["window"]["timezone"] == "UTC"
    assert kathmandu["window"]["timezone"] == "Asia/Kathmandu"
    # The same stored instant, so the totals agree even though the day edge differs.
    assert sum(b["totals"]["total_tokens"] for b in utc["buckets"]) == sum(
        b["totals"]["total_tokens"] for b in kathmandu["buckets"]
    )