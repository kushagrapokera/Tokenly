"""Tests for resolving Cline CLI's data directory without hardcoding platform paths."""

import subprocess
from pathlib import Path

import pytest

from collectors.cline.locator import (
    platform_default_data_directory,
    resolve_data_directory,
    resolve_database_path,
    resolve_sessions_directory,
)
from config.settings import Settings


def test_explicit_setting_wins(tmp_path: Path) -> None:
    resolved = resolve_data_directory(Settings(cline_data_dir=tmp_path / "data"))

    assert resolved == tmp_path / "data"


def test_default_points_at_the_documented_location(monkeypatch: pytest.MonkeyPatch) -> None:
    # An inherited CLINE_DATA_DIR would answer for the platform default instead.
    monkeypatch.delenv("CLINE_DATA_DIR", raising=False)

    assert resolve_data_directory(Settings()) == platform_default_data_directory()


def test_sessions_directory_is_the_data_directory_plus_sessions(tmp_path: Path) -> None:
    settings = Settings(cline_data_dir=tmp_path)

    assert resolve_sessions_directory(settings) == tmp_path / "sessions"


def test_database_path_is_the_data_directory_plus_db_index(tmp_path: Path) -> None:
    settings = Settings(cline_data_dir=tmp_path)

    assert resolve_database_path(settings) == tmp_path / "db" / "sessions.db"


def test_resolution_never_runs_the_cline_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `cline config --json` prints workspace config, not a data-dir pointer, so
    # resolution must stay deterministic and work without the CLI installed.
    def refuse_to_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("resolving the data directory must not shell out")

    monkeypatch.setattr(subprocess, "run", refuse_to_run)
    monkeypatch.delenv("CLINE_DATA_DIR", raising=False)

    assert resolve_data_directory(Settings(cline_data_dir=tmp_path)) == tmp_path
    assert resolve_data_directory(Settings()) == platform_default_data_directory()
