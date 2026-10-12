"""Dashboard date and platform queries include the correct historical records."""

from datetime import datetime, timedelta, timezone

import pytest

from tests.usage_fixtures import make_record, seed

END = datetime(2026, 10, 14, tzinfo=timezone.utc)


@pytest.fixture
def dashboard_history(app):
    seed(
        app,
        [
            make_record("recent", END - timedelta(days=2), input_tokens=100, output_tokens=0),
            make_record("month", END - timedelta(days=20), input_tokens=200, output_tokens=0),
            make_record("quarter", END - timedelta(days=60), input_tokens=400, output_tokens=0),
            make_record("too-old", END - timedelta(days=95), input_tokens=800, output_tokens=0),
            make_record(
                "cline-month",
                END - timedelta(days=20),
                platform="cline",
                input_tokens=50,
                output_tokens=0,
            ),
        ],
    )


@pytest.mark.parametrize(("days", "expected_total"), [(7, 100), (30, 300), (90, 700)])
@pytest.mark.parametrize("endpoint", ["summary", "models", "timeline"])
def test_selected_range_preserves_older_platform_usage(
    client, dashboard_history, days, expected_total, endpoint
):
    response = client.get(
        f"/api/usage/{endpoint}",
        params={
            "range": "custom",
            "start": (END - timedelta(days=days)).isoformat(),
            "end": END.isoformat(),
            "timezone": "UTC",
            "platform": "opencode",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["platform"] == "opencode"
    if endpoint == "summary":
        actual_total = payload["totals"]["total_tokens"]
    else:
        records = payload["models" if endpoint == "models" else "buckets"]
        actual_total = sum(record["totals"]["total_tokens"] for record in records)
    assert actual_total == expected_total
    if endpoint == "timeline":
        assert len(payload["buckets"]) == days


def test_platform_selection_isolates_the_other_platform(client, dashboard_history):
    response = client.get(
        "/api/usage/timeline",
        params={
            "range": "custom",
            "start": (END - timedelta(days=30)).isoformat(),
            "end": END.isoformat(),
            "platform": "cline",
        },
    )

    assert response.status_code == 200
    assert sum(bucket["totals"]["total_tokens"] for bucket in response.json()["buckets"]) == 50
