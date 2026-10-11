"""Shared test fixtures: an app wired to a temporary SQLite database."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.settings import Settings
from database.connection import Base
from main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings pointing at a throwaway SQLite file inside the test's temp directory."""
    return Settings(database_path=tmp_path / "test.db", log_level="WARNING")


@pytest.fixture
def app(test_settings: Settings) -> Iterator[FastAPI]:
    """An application instance whose schema has been created.

    The schema is created by the fixture rather than by `create_app` because production
    runs Alembic migrations; creating tables in the factory would mean two sources of
    truth for the schema, and the migrations would stop being exercised.
    """
    application = create_app(test_settings)
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Test client for the temporary application."""
    with TestClient(app) as test_client:
        yield test_client
