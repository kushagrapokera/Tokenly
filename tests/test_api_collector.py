"""Tests for the collector endpoints and for how the API surfaces errors.

The status endpoint and the rescan endpoint are the dashboard's only view of the
collection pipeline, so they are tested against a collector the test controls rather
than against a real OpenCode installation, which may or may not be present.
"""

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from collectors.base import BaseCollector, ScanOutcome
from schemas.usage import DiscoveryResult, UsageRecord
from tests.usage_fixtures import (
    body,
    collectors_of,
    first_run,
    make_record,
    rescan_runs,
)

UTC = timezone.utc
SCAN_MOMENT = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


class StubCollector(BaseCollector):
    """A collector backed by values the test supplies, including failure cases."""

    def __init__(
        self,
        records: list[UsageRecord] | None = None,
        *,
        available: bool = True,
        detail: str = "2 sessions",
        fail_with: Exception | None = None,
    ) -> None:
        self._records = records or []
        self._available = available
        self._detail = detail
        self._fail_with = fail_with
        self.scan_count = 0
        self.checkpoints_seen: list[str | None] = []

    @property
    def platform(self) -> str:
        return "opencode"

    def discover(self) -> DiscoveryResult:
        return DiscoveryResult(
            platform=self.platform,
            available=self._available,
            source_path="/stub/opencode.db",
            storage_format="sqlite",
            detail=self._detail,
        )

    def collect_history(self) -> list[UsageRecord]:
        return list(self._records)

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        self.checkpoints_seen.append(checkpoint)
        return list(self._records)

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        self.scan_count += 1
        self.checkpoints_seen.append(checkpoint)
        if self._fail_with is not None:
            raise self._fail_with
        return ScanOutcome(records=list(self._records))


@pytest.fixture
def stub_collector() -> StubCollector:
    """A collector holding two records from a single model."""
    return StubCollector(
        [
            make_record("stub_1", SCAN_MOMENT, input_tokens=100, output_tokens=10),
            make_record("stub_2", SCAN_MOMENT, input_tokens=50, output_tokens=5),
        ]
    )


@pytest.fixture
def collector_app(app: FastAPI, stub_collector: StubCollector) -> FastAPI:
    """An application whose only collector is the stub under the test's control."""
    app.state.collectors = [stub_collector]
    return app


@pytest.fixture
def collector_client(collector_app: FastAPI) -> Iterator[TestClient]:
    """Client for the application backed by the stub collector."""
    with TestClient(collector_app) as test_client:
        yield test_client


def test_status_reports_the_collector_is_available(collector_client: TestClient) -> None:
    response = collector_client.get("/api/collector/status")

    assert response.status_code == 200
    status = collectors_of(response)[0]
    assert status["platform"] == "opencode"
    assert status["available"] is True
    assert status["source_path"] == "/stub/opencode.db"


def test_status_of_a_never_scanned_collector_says_so(collector_client: TestClient) -> None:
    status = collectors_of(collector_client.get("/api/collector/status"))[0]

    assert status["status"] == "never_scanned"
    assert status["checkpoint"] is None
    assert status["last_scan_at"] is None
    assert status["stored_events"] == 0


def test_status_of_an_unavailable_collector_is_reported_not_raised(
    app: FastAPI,
) -> None:
    app.state.collectors = [StubCollector(available=False, detail="no database file")]

    with TestClient(app) as missing_client:
        response = missing_client.get("/api/collector/status")

    assert response.status_code == 200
    status = collectors_of(response)[0]
    assert status["available"] is False
    assert status["detail"] == "no database file"


def test_status_of_one_platform_is_addressable(collector_client: TestClient) -> None:
    response = collector_client.get("/api/collector/status/opencode")

    assert response.status_code == 200
    assert body(response)["platform"] == "opencode"


def test_status_of_an_unknown_platform_is_a_404_naming_the_known_ones(
    collector_client: TestClient,
) -> None:
    response = collector_client.get("/api/collector/status/codex")

    assert response.status_code == 404
    assert body(response)["error"] == "NotFoundError"
    assert "opencode" in body(response)["detail"]


def test_rescan_stores_the_collectors_records(collector_client: TestClient) -> None:
    response = collector_client.post("/api/collector/rescan")

    assert response.status_code == 200
    run = first_run(response)
    assert run["platform"] == "opencode"
    assert run["succeeded"] is True
    assert run["inserted"] == 2
    assert run["stored"] == 2


def test_rescan_leaves_the_database_readable_by_the_usage_endpoints(
    collector_client: TestClient,
) -> None:
    collector_client.post("/api/collector/rescan")

    summary = collector_client.get("/api/usage/summary", params={"range": "all_time"})

    assert body(summary)["completeness"]["request_count"] == 2


def test_rescan_records_progress_so_status_reflects_it(collector_client: TestClient) -> None:
    collector_client.post("/api/collector/rescan")

    status = collectors_of(collector_client.get("/api/collector/status"))[0]
    assert status["status"] == "idle"
    assert status["checkpoint"] is not None
    assert status["stored_events"] == 2


def test_rescan_runs_a_full_scan_rather_than_resuming(collector_client: TestClient) -> None:
    collector_client.post("/api/collector/rescan")
    collector_client.post("/api/collector/rescan")

    runs = rescan_runs(collector_client.post("/api/collector/rescan"))
    assert runs[0]["mode"] == "historical"


def test_repeated_rescans_do_not_inflate_the_stored_total(
    collector_client: TestClient,
) -> None:
    collector_client.post("/api/collector/rescan")
    first = body(collector_client.get("/api/usage/summary", params={"range": "all_time"}))

    for _ in range(3):
        collector_client.post("/api/collector/rescan")
    later = body(collector_client.get("/api/usage/summary", params={"range": "all_time"}))

    assert later["totals"] == first["totals"]
    assert later["completeness"] == first["completeness"]


def test_rescan_of_one_platform_is_addressable(collector_client: TestClient) -> None:
    response = collector_client.post("/api/collector/rescan/opencode")

    assert response.status_code == 200
    assert body(response)["platform"] == "opencode"


def test_rescan_of_an_unknown_platform_is_a_404(collector_client: TestClient) -> None:
    response = collector_client.post("/api/collector/rescan/codex")

    assert response.status_code == 404
    assert body(response)["error"] == "NotFoundError"


def test_a_failed_scan_is_reported_rather_than_raised(app: FastAPI) -> None:
    app.state.collectors = [StubCollector(fail_with=RuntimeError("source is locked"))]

    with TestClient(app) as failing_client:
        response = failing_client.post("/api/collector/rescan")

    assert response.status_code == 200
    run = first_run(response)
    assert run["succeeded"] is False
    assert run["error_message"] == "source is locked"


def test_a_failed_scan_is_reflected_in_the_collector_status(app: FastAPI) -> None:
    app.state.collectors = [StubCollector(fail_with=RuntimeError("source is locked"))]

    with TestClient(app) as failing_client:
        failing_client.post("/api/collector/rescan")
        status = collectors_of(failing_client.get("/api/collector/status"))[0]

    assert status["status"] == "error"
    assert status["checkpoint"] is None
