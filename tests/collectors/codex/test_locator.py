"""Tests for the Codex locator's resolution order: setting -> env -> default."""

from pathlib import Path

from collectors.codex.locator import (
    CODEX_HOME_ENV_VAR,
    SESSIONS_DIRECTORY_NAME,
    platform_default_home_directory,
    resolve_home_directory,
    resolve_sessions_directory,
)
from config.settings import Settings


def test_an_explicit_setting_wins_over_the_environment(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CODEX_HOME_ENV_VAR, str(tmp_path / "from-env"))
    settings = Settings(codex_home=tmp_path / "from-setting")

    assert resolve_home_directory(settings) == tmp_path / "from-setting"


def test_the_environment_is_used_when_no_setting_is_given(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CODEX_HOME_ENV_VAR, str(tmp_path / "from-env"))

    assert resolve_home_directory(Settings()) == tmp_path / "from-env"


def test_the_platform_default_is_used_when_neither_is_set(monkeypatch) -> None:
    monkeypatch.delenv(CODEX_HOME_ENV_VAR, raising=False)

    assert resolve_home_directory(Settings()) == platform_default_home_directory()


def test_the_default_home_is_the_documented_dot_codex(monkeypatch) -> None:
    monkeypatch.delenv(CODEX_HOME_ENV_VAR, raising=False)

    assert platform_default_home_directory().name == ".codex"


def test_the_sessions_directory_sits_under_the_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(CODEX_HOME_ENV_VAR, raising=False)
    settings = Settings(codex_home=tmp_path / "codex")

    sessions = resolve_sessions_directory(settings)

    assert sessions == tmp_path / "codex" / SESSIONS_DIRECTORY_NAME


def test_an_env_relative_path_is_expanded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(CODEX_HOME_ENV_VAR, "~/codex-home")

    resolved = resolve_home_directory(Settings())

    assert not str(resolved).startswith("~")
    assert resolved.name == "codex-home"
