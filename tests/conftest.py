"""Shared test fixtures: an app wired to a temporary SQLite database."""

from collections.abc import Iterator
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
