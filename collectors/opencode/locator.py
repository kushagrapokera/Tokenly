"""Locate OpenCode's local data directory without hardcoding any platform path.

OpenCode's data directory is configurable, so the only reliable way to find it is to
ask OpenCode itself. We shell out to the CLI and fall back to the documented default
per platform, logging whenever the fallback is used.
"""

import logging
import os
import subprocess
from pathlib import Path

from config.settings import Settings
from errors.exceptions import CollectorSourceUnreadableError

logger = logging.getLogger(__name__)

DATABASE_FILE_NAME = "opencode.db"


def resolve_data_directory(settings: Settings) -> Path:
    """Return OpenCode's data directory, preferring an explicit setting over the CLI."""
    if settings.opencode_data_dir is not None:
        logger.info("using configured opencode data directory %s", settings.opencode_data_dir)
        return settings.opencode_data_dir.expanduser()

    cli_directory = _read_data_directory_from_cli(settings)
    if cli_directory is not None:
        return cli_directory

    fallback = platform_default_data_directory()
    logger.warning(
        "opencode CLI did not report a data directory; falling back to the platform default %s",
        fallback,
    )
    return fallback


def resolve_database_path(settings: Settings) -> Path:
    """Return the full path of OpenCode's SQLite database file."""
    return resolve_data_directory(settings) / DATABASE_FILE_NAME


def _read_data_directory_from_cli(settings: Settings) -> Path | None:
    """Ask `opencode debug paths` for the data directory; None when the CLI cannot answer.

    Never raises: a missing CLI or an unexpected output shape must degrade to the
    platform default rather than break discovery.
    """
    command = [settings.opencode_command, "debug", "paths"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.opencode_command_timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("could not run %s: %s", " ".join(command), error)
        return None

    if completed.returncode != 0:
        logger.warning(
            "%s exited with code %s: %s",
            " ".join(command),
            completed.returncode,
            completed.stderr.strip(),
        )
        return None

    directory = parse_data_directory(completed.stdout)
    if directory is None:
        logger.warning("no 'data' line in %s output", " ".join(command))
    return directory


def parse_data_directory(output: str) -> Path | None:
    """Pull the data directory out of `opencode debug paths` output.

    The CLI prints space-aligned columns (`data       /home/me/.local/share/opencode`),
    so split on any whitespace run rather than a single tab.
    """
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "data":
            return Path(fields[1]).expanduser()
    return None


def platform_default_data_directory() -> Path:
    """Return the documented default data directory for the current platform."""
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "opencode"
        return Path.home() / "AppData" / "Local" / "opencode"

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "opencode"
    return Path.home() / ".local" / "share" / "opencode"


def require_database_path(settings: Settings) -> Path:
    """Return the database path, raising a contextual error when the file is missing."""
    database_path = resolve_database_path(settings)
    if not database_path.is_file():
        raise CollectorSourceUnreadableError(
            str(database_path), FileNotFoundError("no OpenCode database at this path")
        )
    return database_path
