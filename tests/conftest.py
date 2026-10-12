"""Shared test fixtures: an app wired to a temporary SQLite database."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.settings import Settings
from main import create_app

@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings for an app that collects nothing unless a test asks it to.

    Automatic collection is off because these tests are about the API, not about
    scanning: leaving it on would read the developer's real OpenCode and Cline
    stores into a throwaway database on every test. The scheduler and the
    coordinator are exercised directly in `test_sync_coordinator.py` and
    `test_sync_scheduler.py`.
    """
    return Settings(
        database_path=tmp_path / "test.db",
        log_level="WARNING",
        sync_enabled=False,
    )


@pytest.fixture
def app(test_settings: Settings) -> Iterator[FastAPI]:
    """An application instance with a throwaway database and no background sync."""
    application = create_app(test_settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Test client for the temporary application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_for_origins(
    tmp_path: Path,
) -> Iterator[Callable[[list[str]], TestClient]]:
    """Build a client whose app allows exactly the given CORS origins.

    The default allowlist is empty, so a test that cares about cross-origin access
    has to opt in explicitly rather than inherit an origin nobody serves from.
    """
    applications: list[FastAPI] = []
    clients: list[TestClient] = []

    def build(origins: list[str]) -> TestClient:
        application = create_app(
            Settings(
                database_path=tmp_path / f"cors-{len(applications)}.db",
                cors_allow_origins=origins,
                log_level="WARNING",
                sync_enabled=False,
            )
        )
        applications.append(application)
        test_client = TestClient(application)
        test_client.__enter__()
        clients.append(test_client)
        return test_client

    yield build

    for test_client, application in zip(clients, applications, strict=True):
        test_client.__exit__(None, None, None)
        application.state.engine.dispose()
