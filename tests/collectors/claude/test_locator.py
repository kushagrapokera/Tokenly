"""Tests for the Claude Code locator's resolution order: setting -> env -> default."""

from pathlib import Path

from collectors.claude.locator import (
    CLAUDE_CONFIG_ENV_VAR,
    PROJECTS_DIRECTORY_NAME,
    platform_default_data_directory,
    resolve_data_directory,
    resolve_projects_directory,
)
from config.settings import Settings


def test_an_explicit_setting_wins_over_the_environment(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CLAUDE_CONFIG_ENV_VAR, str(tmp_path / "from-env"))
    settings = Settings(claude_data_dir=tmp_path / "from-setting")

    assert resolve_data_directory(settings) == tmp_path / "from-setting"


def test_the_environment_is_used_when_no_setting_is_given(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CLAUDE_CONFIG_ENV_VAR, str(tmp_path / "from-env"))

    assert resolve_data_directory(Settings()) == tmp_path / "from-env"


def test_the_platform_default_is_used_when_neither_is_set(monkeypatch) -> None:
    monkeypatch.delenv(CLAUDE_CONFIG_ENV_VAR, raising=False)

    assert resolve_data_directory(Settings()) == platform_default_data_directory()


def test_the_default_directory_is_the_documented_dot_claude(monkeypatch) -> None:
    monkeypatch.delenv(CLAUDE_CONFIG_ENV_VAR, raising=False)

    assert platform_default_data_directory().name == ".claude"


def test_the_projects_directory_sits_under_the_data_directory(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(CLAUDE_CONFIG_ENV_VAR, raising=False)
    settings = Settings(claude_data_dir=tmp_path / "claude")

    projects = resolve_projects_directory(settings)

    assert projects == tmp_path / "claude" / PROJECTS_DIRECTORY_NAME


def test_an_env_relative_path_is_expanded(monkeypatch) -> None:
    monkeypatch.setenv(CLAUDE_CONFIG_ENV_VAR, "~/claude-home")

    resolved = resolve_data_directory(Settings())

    assert not str(resolved).startswith("~")
    assert resolved.name == "claude-home"
