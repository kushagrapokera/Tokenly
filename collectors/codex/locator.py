"""Locate Codex CLI's local data directory without hardcoding any platform path.

Codex CLI keeps everything under `$CODEX_HOME` (defaulting to `~/.codex`), so the
resolution order is the same posture as Claude and Cline: an explicit setting
first, then the documented `CODEX_HOME` environment variable, then the platform
default. Nothing here shells out to the `codex` binary — it exposes no data-dir
query command, so shelling out could only ever return what this order already
knows (see `docs/codex_storage_analysis.md` §7).
"""

import logging
import os
from pathlib import Path

from config.settings import Settings

logger = logging.getLogger(__name__)

SESSIONS_DIRECTORY_NAME = "sessions"
CODEX_HOME_ENV_VAR = "CODEX_HOME"


def resolve_home_directory(settings: Settings) -> Path:
    """Return Codex CLI's home directory, preferring an explicit setting."""
    if settings.codex_home is not None:
        logger.info("using configured codex home directory %s", settings.codex_home)
        return settings.codex_home.expanduser()

    from_environment = _read_home_directory_from_environment()
    if from_environment is not None:
        return from_environment

    fallback = platform_default_home_directory()
    logger.info("no codex home directory configured; using platform default %s", fallback)
    return fallback


def resolve_sessions_directory(settings: Settings) -> Path:
    """Return the directory holding per-session rollout files."""
    return resolve_home_directory(settings) / SESSIONS_DIRECTORY_NAME


def _read_home_directory_from_environment() -> Path | None:
    """Return `CODEX_HOME` when set; None otherwise."""
    configured = os.environ.get(CODEX_HOME_ENV_VAR)
    if not configured:
        return None
    directory = Path(configured).expanduser()
    logger.info("codex home directory from environment: %s", directory)
    return directory


def platform_default_home_directory() -> Path:
    """Return Codex CLI's documented default home directory for this platform."""
    return Path.home() / ".codex"
