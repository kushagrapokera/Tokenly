"""Tests for how the API is exposed: origin restrictions and error shapes.

The API serves its own dashboard from the same origin, so by default it must refuse
every cross-origin request. Getting that wrong in either direction is a real problem:
too strict and a separately-hosted page cannot load, too loose and any page the user
visits could read their usage history.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient

from config.settings import Settings
from tests.usage_fixtures import body

FOREIGN_ORIGIN = "http://evil.example"
CONFIGURED_ORIGIN = "http://localhost:4173"


def test_a_cross_origin_request_is_refused_by_default(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": FOREIGN_ORIGIN})

    assert "access-control-allow-origin" not in response.headers


def test_the_api_defaults_to_allowing_no_origin() -> None:
    assert Settings().cors_allow_origins == []


def test_a_preflight_from_a_foreign_origin_is_refused_by_default(client: TestClient) -> None:
    response = client.options(
        "/api/usage/summary",
        headers={"Origin": FOREIGN_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_a_configured_origin_is_allowed(
    client_for_origins: Callable[[list[str]], TestClient],
) -> None:
    allowed_client = client_for_origins([CONFIGURED_ORIGIN])

    response = allowed_client.get("/api/health", headers={"Origin": CONFIGURED_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == CONFIGURED_ORIGIN


def test_a_configured_origin_still_refuses_every_other_origin(
    client_for_origins: Callable[[list[str]], TestClient],
) -> None:
    allowed_client = client_for_origins([CONFIGURED_ORIGIN])

    rejected = allowed_client.get("/api/health", headers={"Origin": FOREIGN_ORIGIN})

    assert "access-control-allow-origin" not in rejected.headers


def test_a_configured_origin_may_answer_a_preflight(
    client_for_origins: Callable[[list[str]], TestClient],
) -> None:
    allowed_client = client_for_origins([CONFIGURED_ORIGIN])

    response = allowed_client.options(
        "/api/usage/summary",
        headers={"Origin": CONFIGURED_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-methods") == "GET"


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
