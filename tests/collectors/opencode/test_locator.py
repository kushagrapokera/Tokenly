"""Tests for resolving OpenCode's data directory without hardcoding platform paths."""

import subprocess
from pathlib import Path

import pytest

from collectors.opencode.locator import (
    parse_data_directory,
    platform_default_data_directory,
    require_database_path,
    resolve_data_directory,
    resolve_database_path,
)
from config.settings import Settings
from errors.exceptions import CollectorSourceUnreadableError


def test_data_directory_comes_from_the_cli_when_it_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0] if args else kwargs["args"],
            returncode=0,
            stdout="home  /home/dev\ndata  /custom/opencode-data\nbin   /bin\n",
            stderr="",
        ),
    )

    resolved = resolve_data_directory(Settings())

    assert resolved == Path("/custom/opencode-data")


def test_explicit_setting_wins_over_the_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("the CLI must not be consulted when the setting is explicit")

    monkeypatch.setattr(subprocess, "run", fail)

    resolved = resolve_data_directory(Settings(opencode_data_dir=tmp_path / "data"))

    assert resolved == tmp_path / "data"


def test_falls_back_to_the_platform_default_when_the_cli_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="command not found"
        ),
    )

    assert resolve_data_directory(Settings()) == platform_default_data_directory()


def test_a_missing_cli_binary_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("opencode")

    monkeypatch.setattr(subprocess, "run", raise_missing)

    assert resolve_data_directory(Settings()) == platform_default_data_directory()


def test_a_timeout_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="opencode", timeout=1)

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    assert resolve_data_directory(Settings()) == platform_default_data_directory()


@pytest.mark.parametrize(
    "output",
    [
        "home  /home/dev\ndata  /home/dev/data\nbin   /bin\n",
        "data\t/home/dev/data\n",
        "data       /home/dev/data       \n",
        "  data   /home/dev/data  \n",
    ],
)
def test_data_line_is_parsed_across_the_formats_opencode_prints(output: str) -> None:
    assert parse_data_directory(output) == Path("/home/dev/data")


def test_output_without_a_data_line_yields_nothing() -> None:
    assert parse_data_directory("home  /home/dev\nbin  /bin\n") is None


def test_database_path_is_the_data_directory_plus_the_database_file(tmp_path: Path) -> None:
    settings = Settings(opencode_data_dir=tmp_path)

    assert resolve_database_path(settings) == tmp_path / "opencode.db"


def test_require_database_path_names_the_missing_file(tmp_path: Path) -> None:
    settings = Settings(opencode_data_dir=tmp_path)

    with pytest.raises(CollectorSourceUnreadableError) as caught:
        require_database_path(settings)

    assert str(tmp_path / "opencode.db") in str(caught.value)
