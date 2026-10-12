"""Tests for the usage endpoints.

Each test asks an endpoint the question the dashboard will ask, then checks the answer
against what was seeded through the real storage path. Assertions are on the response a
client receives, not on the aggregation internals, so the contract under test is the one
Phase 9 will depend on.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.usage_fixtures import body, bucket_labels, make_record, seed, totals_of

UTC = timezone.utc

BASE_MOMENT = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def usage_app(app: FastAPI) -> FastAPI:
    """An app holding a known set of records spread across days, months, and models.

    The five records give every dimension something to distinguish: two providers, two
    models, three months of history, one record whose totals were never reported, and
    cache reads on two of the three `example-model` rows so the cache rates are non-zero.
    """
    seed(
        app,
        [
            make_record(
                "msg_1",
                BASE_MOMENT,
                input_tokens=100,
                output_tokens=10,
                cache_read_tokens=60,
            ),
            make_record(
                "msg_2",
                BASE_MOMENT - timedelta(hours=2),
                input_tokens=50,
                output_tokens=5,
                cache_read_tokens=40,
                cache_write_tokens=5,
            ),
            make_record(
                "msg_3", BASE_MOMENT - timedelta(days=3), input_tokens=200, output_tokens=20
            ),
            make_record(
                "msg_4",
                BASE_MOMENT - timedelta(days=40),
                model_id="other-model",
                provider_id="opencode",
                input_tokens=7,
                output_tokens=3,
            ),
            make_record(
                "msg_5",
                BASE_MOMENT - timedelta(days=70),
                model_id="other-model",
                provider_id="opencode",
                input_tokens=None,
                output_tokens=None,
                consumption_tokens=None,
                cache_read_tokens=None,
            ),
        ],
    )
    return app


@pytest.fixture
def usage_client(usage_app: FastAPI) -> Iterator[TestClient]:
    """Client for the seeded application."""
    with TestClient(usage_app) as test_client:
        yield test_client


@pytest.fixture
def empty_client(app: FastAPI) -> Iterator[TestClient]:
    """Client for an application whose database holds no usage at all."""
    with TestClient(app) as test_client:
        yield test_client


def test_summary_returns_the_totals_of_the_requested_range(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/summary", params={"range": "all_time"})

    assert response.status_code == 200
    # Four records reported tokens summing to 395; the fifth reported none at all, so it
    # adds nothing to any total but is still counted as a request. Two of the four known
    # rows read from cache and two reported zero, so the hit rate is 2/4 — the unknown row
    # is counted as neither. These providers count cache reads outside input_tokens, so
    # the prompt denominator is 357 input plus the 100 cached tokens.
    assert totals_of(response) == {
        "input_tokens": 357,
        "output_tokens": 38,
        "total_tokens": 395,
        "consumption_tokens": 480,
        "cache": {
            "cache_read_tokens": 100,
            "cache_write_tokens": 5,
            "cache_hit_requests": 2,
            "cache_miss_requests": 2,
            "cache_unknown_requests": 1,
            "cache_known_requests": 4,
            "cache_prompt_tokens": 457,
            "request_hit_rate": 2 / 4,
            "token_hit_rate": 100 / 457,
        },
    }


def test_summary_reports_the_window_it_answered_for(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/summary", params={"range": "all_time"})

    window = body(response)["window"]
    assert window["range"] == "all_time"
    assert window["start"] is None
    assert window["end"] is None


def test_summary_defaults_to_all_time_when_no_range_is_given(usage_client: TestClient) -> None:
    with_range = usage_client.get("/api/usage/summary", params={"range": "all_time"})
    without_range = usage_client.get("/api/usage/summary")

    assert totals_of(without_range) == totals_of(with_range)


def test_summary_separates_unknown_totals_from_known_ones(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/summary", params={"range": "all_time"})

    completeness = body(response)["completeness"]
    assert completeness["request_count"] == 5
    assert completeness["known_total_events"] == 4
    assert completeness["unknown_total_events"] == 1
    assert completeness["is_complete"] is False


def test_summary_counts_only_the_records_inside_a_named_range(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/summary",
        params={"range": "custom", "start": "2026-03-01T00:00:00Z", "end": "2026-04-01T00:00:00Z"},
    )

    assert response.status_code == 200
    assert body(response)["completeness"]["request_count"] == 3


def test_summary_narrows_by_provider(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/summary", params={"range": "all_time", "provider_id": "opencode"}
    )

    assert body(response)["completeness"]["request_count"] == 2
    assert body(response)["filters"]["provider_id"] == "opencode"


def test_summary_narrows_by_model(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/summary", params={"range": "all_time", "model_id": "other-model"}
    )

    assert body(response)["completeness"]["request_count"] == 2


def test_summary_builds_calendar_edges_in_the_requested_timezone(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/summary", params={"range": "today", "timezone": "Asia/Kolkata"}
    )

    window = body(response)["window"]
    assert window["timezone"] == "Asia/Kolkata"
    assert window["start"].endswith("Z")
    assert window["end"] > window["start"]


def test_summary_of_an_empty_database_is_all_zeroes_not_an_error(
    empty_client: TestClient,
) -> None:
    response = empty_client.get("/api/usage/summary", params={"range": "all_time"})

    assert response.status_code == 200
    assert totals_of(response)["total_tokens"] == 0
    assert body(response)["completeness"] == {
        "request_count": 0,
        "known_total_events": 0,
        "unknown_total_events": 0,
        "is_complete": True,
    }


def test_summary_rejects_an_unknown_range(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/summary", params={"range": "last_fortnight"})

    assert response.status_code == 400
    assert body(response)["error"] == "UnknownRangeError"
    assert "today" in body(response)["detail"]


def test_summary_rejects_an_unknown_timezone(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/summary", params={"range": "today", "timezone": "Mars/Olympus"}
    )

    assert response.status_code == 400
    assert body(response)["error"] == "InvalidTimezoneError"


def test_summary_rejects_a_custom_range_without_bounds(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/summary", params={"range": "custom"})

    assert response.status_code == 400
    assert body(response)["error"] == "InvalidTimeRangeError"


def test_summary_rejects_an_inverted_custom_range(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/summary",
        params={
            "range": "custom",
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-03-01T00:00:00Z",
        },
    )

    assert response.status_code == 400
    assert body(response)["error"] == "InvalidTimeRangeError"


def test_daily_returns_one_bucket_per_day_of_the_range(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/daily", params={"range": "last_7_days"})

    assert response.status_code == 200
    assert len(bucket_labels(response)) == 7


def test_daily_buckets_are_labelled_by_calendar_day(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/daily", params={"range": "last_7_days"})

    assert body(response)["buckets"][0]["label"].count("-") == 2


def test_daily_totals_reconcile_with_the_summary_for_the_same_range(
    usage_client: TestClient,
) -> None:
    timeline = usage_client.get("/api/usage/daily", params={"range": "last_7_days"})
    summary = usage_client.get("/api/usage/summary", params={"range": "last_7_days"})

    summed = sum(bucket["totals"]["total_tokens"] for bucket in body(timeline)["buckets"])
    assert summed == totals_of(summary)["total_tokens"]


def test_monthly_returns_one_bucket_per_month_of_the_range(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/monthly", params={"range": "current_year"})

    assert response.status_code == 200
    assert all(len(label) == 7 for label in bucket_labels(response))


def test_monthly_defaults_to_the_current_year(usage_client: TestClient) -> None:
    default = usage_client.get("/api/usage/monthly")
    explicit = usage_client.get("/api/usage/monthly", params={"range": "current_year"})

    assert body(default)["window"]["range"] == "current_year"
    assert bucket_labels(default) == bucket_labels(explicit)


def test_yearly_returns_one_bucket_per_year(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/yearly", params={"range": "all_time"})

    assert response.status_code == 200
    assert all(len(label) == 4 for label in bucket_labels(response))


def test_timeline_reports_the_granularity_it_used(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/timeline", params={"range": "last_7_days", "granularity": "month"}
    )

    assert body(response)["granularity"] == "month"


def test_timeline_rejects_an_unsupported_granularity(usage_client: TestClient) -> None:
    response = usage_client.get(
        "/api/usage/timeline", params={"range": "last_7_days", "granularity": "hour"}
    )

    assert response.status_code == 400
    assert body(response)["error"] == "InvalidGranularityError"


def test_timeline_of_an_unbounded_range_falls_back_to_a_bounded_one(
    usage_client: TestClient,
) -> None:
    response = usage_client.get("/api/usage/timeline", params={"range": "all_time"})

    assert response.status_code == 200
    assert len(bucket_labels(response)) >= 1


def test_models_are_grouped_by_provider_and_model(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/models", params={"range": "all_time"})

    assert response.status_code == 200
    pairs = [(model["provider_id"], model["model_id"]) for model in body(response)["models"]]
    assert ("openrouter", "example-model") in pairs
    assert ("opencode", "other-model") in pairs


def test_models_are_ordered_by_total_tokens_descending(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/models", params={"range": "all_time"})

    totals = [model["totals"]["total_tokens"] for model in body(response)["models"]]
    assert totals == sorted(totals, reverse=True)


def test_models_totals_reconcile_with_the_summary(usage_client: TestClient) -> None:
    models = usage_client.get("/api/usage/models", params={"range": "all_time"})
    summary = usage_client.get("/api/usage/summary", params={"range": "all_time"})

    summed = sum(model["totals"]["total_tokens"] for model in body(models)["models"])
    assert summed == totals_of(summary)["total_tokens"]


def test_models_report_their_own_unknown_counts(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/models", params={"range": "all_time"})

    unknown = {
        model["model_id"]: model["unknown_total_events"] for model in body(response)["models"]
    }
    assert unknown["other-model"] == 1
    assert unknown["example-model"] == 0


def test_models_of_an_empty_database_return_an_empty_list(empty_client: TestClient) -> None:
    response = empty_client.get("/api/usage/models", params={"range": "all_time"})

    assert response.status_code == 200
    assert body(response)["models"] == []


def test_every_usage_endpoint_reports_cache_effectiveness(usage_client: TestClient) -> None:
    """Cache figures reach the wire on every totals-bearing endpoint, not just one.

    Each response nests its totals differently — summary has one at the top level, the
    timeline has one per bucket, and models one per row. All three shapes have to expose
    the same cache fields, or a client has to special-case which endpoint it is reading.
    """
    expected = {
        "cache_read_tokens",
        "cache_write_tokens",
        "cache_hit_requests",
        "cache_miss_requests",
        "cache_unknown_requests",
        "cache_known_requests",
        "cache_prompt_tokens",
        "request_hit_rate",
        "token_hit_rate",
    }
    assert set(totals_of(usage_client.get("/api/usage/summary"))["cache"]) == expected

    daily = body(usage_client.get("/api/usage/daily"))
    assert daily["buckets"], "the daily timeline returned no buckets to check"
    for bucket in daily["buckets"]:
        assert set(bucket["totals"]["cache"]) == expected, bucket["label"]

    for model in body(usage_client.get("/api/usage/models"))["models"]:
        assert set(model["totals"]["cache"]) == expected, model["model_id"]


def test_models_report_cache_per_model_and_provider(usage_client: TestClient) -> None:
    response = usage_client.get("/api/usage/models", params={"range": "all_time"})

    cache = {
        (model["provider_id"], model["model_id"]): model["totals"]["cache"]
        for model in body(response)["models"]
    }
    hit = cache[("openrouter", "example-model")]
    assert hit["cache_read_tokens"] == 100
    assert hit["cache_hit_requests"] == 2
    assert hit["cache_write_tokens"] == 5
    # Additive: the prompt denominator is each row's input plus its own cached tokens,
    # so 160 + 90 + 200 across the three rows.
    assert hit["cache_prompt_tokens"] == 450
    assert hit["request_hit_rate"] == 2 / 3
    assert hit["token_hit_rate"] == 100 / 450


def test_cache_rates_are_null_without_data(empty_client: TestClient) -> None:
    """An empty range reports absent rates, so a client cannot read 0% as a real answer."""
    response = empty_client.get("/api/usage/summary", params={"range": "all_time"})

    cache = totals_of(response)["cache"]
    assert cache["request_hit_rate"] is None
    assert cache["token_hit_rate"] is None
    assert cache["cache_read_tokens"] == 0


def test_every_usage_endpoint_returns_the_same_envelope(usage_client: TestClient) -> None:
    for path in ("/api/usage/summary", "/api/usage/models", "/api/usage/daily"):
        payload = body(usage_client.get(path))

        assert set(payload) >= {"window", "filters", "generated_at"}
