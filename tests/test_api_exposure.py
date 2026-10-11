"""Tests for how the API is exposed: origin restrictions and error shapes.

The API serves a dashboard running on a different local port, so cross-origin access has
to work for the local frontend and fail for everything else. Getting that wrong in either
direction is a real problem: too strict and the dashboard cannot load, too loose and any
page the user visits could read their usage history.
"""

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings
from tests.usage_fixtures import body

LOCAL_ORIGIN = "http://localhost:5173"
FOREIGN_ORIGIN = "http://evil.example"


def test_the_local_frontend_origin_is_allowed(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": LOCAL_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == LOCAL_ORIGIN


def test_a_foreign_origin_is_not_allowed(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": FOREIGN_ORIGIN})

    assert "access-control-allow-origin" not in response.headers


def test_a_preflight_from_the_local_frontend_is_allowed(client: TestClient) -> None:
    response = client.options(
        "/api/usage/summary",
        headers={"Origin": LOCAL_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-methods") == "GET"


def test_a_preflight_from_a_foreign_origin_is_not_allowed(client: TestClient) -> None:
    response = client.options(
        "/api/usage/summary",
        headers={"Origin": FOREIGN_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_the_allowed_origins_are_configurable(tmp_path_factory: pytest.TempPathFactory) -> None:
    from main import create_app

    settings = Settings(
        database_path=tmp_path_factory.mktemp("db") / "custom.db",
        cors_allow_origins=["http://localhost:4173"],
        log_level="WARNING",
    )

    with TestClient(create_app(settings)) as custom_client:
        allowed = custom_client.get("/api/health", headers={"Origin": "http://localhost:4173"})
        rejected = custom_client.get("/api/health", headers={"Origin": LOCAL_ORIGIN})

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:4173"
    assert "access-control-allow-origin" not in rejected.headers


def test_the_api_defaults_to_binding_loopback() -> None:
    assert Settings().host == "127.0.0.1"


def test_an_unknown_path_returns_a_not_found_body(client: TestClient) -> None:
    response = client.get("/api/usage/nonsense")

    assert response.status_code == 404


def test_a_wrong_method_returns_a_method_not_allowed(client: TestClient) -> None:
    response = client.get("/api/collector/rescan")

    assert response.status_code == 405


def test_every_error_body_names_the_error_type(client: TestClient) -> None:
    response = client.get("/api/usage/summary", params={"range": "nonsense"})

    assert body(response) == {
        "detail": body(response)["detail"],
        "error": "UnknownRangeError",
    }
