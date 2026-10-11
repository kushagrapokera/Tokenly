"""Locate Cline CLI's local data directory without hardcoding any platform path.

Cline CLI's data directory is configurable (`--data-dir`, `--config`), so the
only reliable resolution order is: an explicit setting first, then the
platform default. Discovery never shells out: `cline config --json` prints
workspace config rather than a data-dir pointer (verified in
`docs/cline_storage_analysis.md` §13), so probing the binary could only ever
return something the resolver already knows. Collection reads the resolved
directory directly and works whether or not the CLI is installed.
"""

import logging
import os
from pathlib import Path

from config.settings import Settings

logger = logging.getLogger(__name__)

SESSIONS_DATABASE_FILE_NAME = "sessions.db"
SESSIONS_DIRECTORY_NAME = "sessions"


def resolve_data_directory(settings: Settings) -> Path:
    """Return Cline CLI's data directory, preferring an explicit setting."""
    if settings.cline_data_dir is not None:
        logger.info("using configured cline data directory %s", settings.cline_data_dir)
        return settings.cline_data_dir.expanduser()
    fallback = platform_default_data_directory()
    logger.info("no cline data directory configured; using platform default %s", fallback)
    return fallback


def resolve_sessions_directory(settings: Settings) -> Path:
    """Return the directory holding per-session message files."""
    return resolve_data_directory(settings) / SESSIONS_DIRECTORY_NAME


def resolve_database_path(settings: Settings) -> Path:
    """Return the full path of Cline CLI's session index database file."""
    return resolve_data_directory(settings) / "db" / SESSIONS_DATABASE_FILE_NAME


def platform_default_data_directory() -> Path:
    """Return the documented default data directory for the current platform."""
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "cline" / "data"
        return Path.home() / "AppData" / "Local" / "cline" / "data"
    return Path.home() / ".cline" / "data"
