"""Shared test fixtures: an app wired to a temporary SQLite database."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings
from main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings pointing at a throwaway SQLite file inside the test's temp directory."""
    return Settings(database_path=tmp_path / "test.db", log_level="WARNING")


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    """Test client for an application instance backed by the temporary database."""
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client
