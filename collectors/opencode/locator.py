"""Locate OpenCode's local data directory without hardcoding any platform path.

OpenCode's data directory is configurable, so the only reliable way to find it is to
ask OpenCode itself. We shell out to the CLI and fall back to the documented default
per platform, logging whenever the fallback is used.

Asking costs about 600 ms — the CLI has to start, load, and print its paths — and the
answer changes only when the user edits OpenCode's own configuration. Re-asking on
every scan therefore spent 71% of a scan rediscovering a directory. `DataDirectoryResolver`
caches the answer for the life of a collector, which is long-lived; the module-level
functions stay uncached so scripts and tests keep asking for themselves.
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


class DataDirectoryResolver:
    """Resolves OpenCode's data directory once and reuses the answer.

    Four rules make the cache safe rather than merely fast:

    1. **Only a successful answer is cached.** A failed probe is not, so installing
       OpenCode later is noticed on the very next scan. There is nothing to lose by
       this: a probe for a missing binary fails in about 0 ms.
    2. **The cache lives on the collector instance**, so two collectors never share
       an answer and tests stay isolated from each other.
    3. **A cached path that no longer holds the database is re-resolved.** That is
       what covers the user moving their data directory, without needing a TTL and
       the invalidation rules that come with one.
    4. **`invalidate()` exists for a manual rescan**, the moment a user reaches for
       when the numbers look wrong, so the escape hatch costs them nothing.

    Nothing is written to disk. The server is a long-lived local process, so a
    restart costs one probe either way, and a cache file would outlive the process
    and go stale invisibly.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cached_directory: Path | None = None

    def data_directory(self) -> Path:
        """Return the data directory, asking the CLI at most once."""
        if self._settings.opencode_data_dir is not None:
            # Explicitly configured: static by definition, so nothing to cache.
            return self._settings.opencode_data_dir.expanduser()

        if self._cached_directory is not None:
            return self._cached_directory

        reported = _read_data_directory_from_cli(self._settings)
        if reported is None:
            # Not cached: a later scan should notice OpenCode being installed.
            logger.debug("opencode CLI did not report a data directory; asking again next scan")
            return platform_default_data_directory()

        logger.info("opencode reports its data directory at %s", reported)
        self._cached_directory = reported
        return reported

    def database_path(self) -> Path:
        """Return the database path, re-resolving if the cached location went stale."""
        directory = self.data_directory()
        if self._cached_directory is directory and not (directory / DATABASE_FILE_NAME).is_file():
            logger.info(
                "no opencode database at the cached path %s; asking the cli again",
                directory,
            )
            self.invalidate()
            directory = self.data_directory()
        return directory / DATABASE_FILE_NAME

    def require_database_path(self) -> Path:
        """Return the database path, raising a contextual error when it is missing."""
        database_path = self.database_path()
        if not database_path.is_file():
            raise CollectorSourceUnreadableError(
                str(database_path), FileNotFoundError("no OpenCode database at this path")
            )
        return database_path

    def invalidate(self) -> None:
        """Forget the cached answer so the next call asks the CLI again."""
        if self._cached_directory is not None:
            logger.info("forgetting the cached opencode data directory %s", self._cached_directory)
        self._cached_directory = None
