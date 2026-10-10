"""Tests for settings and the database connection helpers."""

from pathlib import Path

import pytest

from config.settings import Settings
from database.connection import create_database_engine, create_session_factory, ping_database
from errors.exceptions import DatabaseUnavailableError


def test_database_url_points_at_the_configured_file(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "stats.db")

    assert settings.database_url.startswith("sqlite:///")
    assert settings.database_url.endswith("/stats.db")


def test_default_settings_identify_the_application() -> None:
    settings = Settings()

    assert settings.app_name == "Tokenly"
    assert settings.port == 8000


def test_engine_creation_makes_the_database_directory(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "dir" / "stats.db"
    settings = Settings(database_path=database_path)

    engine = create_database_engine(settings.database_url, database_path=database_path)

    assert database_path.parent.is_dir()
    engine.dispose()


def test_ping_raises_a_contextual_error_when_database_is_unreachable(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path)  # a directory, not a file
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        with pytest.raises(DatabaseUnavailableError) as caught:
            ping_database(session, settings.database_url)

    assert str(settings.database_url) in str(caught.value)
    assert caught.value.__cause__ is not None
