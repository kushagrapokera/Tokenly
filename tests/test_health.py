"""Tests for the health endpoint."""

from pathlib import Path

from fastapi.testclient import TestClient

from config.settings import Settings
from main import create_app


def test_health_reports_ok_when_database_answers(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database_connected"] is True
    assert body["app"] == "Tokenly"


def test_health_reports_the_configured_version(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.json()["version"] == "1.0.0"


def test_health_returns_service_unavailable_when_database_is_unreachable(
    tmp_path: Path,
) -> None:
    # Pointing the database at a directory makes every connection attempt fail.
    settings = Settings(database_path=tmp_path, log_level="WARNING")

    with TestClient(create_app(settings)) as unreachable_client:
        response = unreachable_client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"


def test_health_failure_body_names_the_error_type(tmp_path: Path) -> None:
    # Every error the API returns names its type, so a client can tell a dead
    # database from a bad request without reading the prose.
    settings = Settings(database_path=tmp_path, log_level="WARNING")

    with TestClient(create_app(settings)) as unreachable_client:
        body = unreachable_client.get("/api/health").json()

    assert body["error"] == "ServiceUnavailableError"
