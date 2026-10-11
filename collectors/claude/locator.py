"""Locate Claude Code's local data directory without hardcoding any platform path.

Claude Code stores session transcripts under `<data_dir>/projects/`, one JSONL
file per session, and resolves its data directory the way most CLIs do: an
environment override first, then the platform default. The collector resolves
in the same order — explicit setting, `CLAUDE_CONFIG_DIR`, platform default —
and logs whenever a fallback is used, so a user with a custom location is
followed rather than silently missed.

Nothing here probes the CLI: unlike OpenCode, Claude Code exposes no
data-dir query command, and shelling out to `claude` for a path it does not
print could only ever return what the resolution order already knows
(the same posture as the Cline locator).
"""

import logging
import os
from pathlib import Path

from config.settings import Settings

logger = logging.getLogger(__name__)

PROJECTS_DIRECTORY_NAME = "projects"


def resolve_data_directory(settings: Settings) -> Path:
    """Return Claude Code's data directory, preferring an explicit setting."""
    if settings.claude_data_dir is not None:
        logger.info("using configured claude data directory %s", settings.claude_data_dir)
        return settings.claude_data_dir.expanduser()

    from_environment = _read_data_directory_from_environment()
    if from_environment is not None:
        return from_environment

    fallback = platform_default_data_directory()
    logger.info("no claude data directory configured; using platform default %s", fallback)
    return fallback


def resolve_projects_directory(settings: Settings) -> Path:
    """Return the directory holding per-session transcript files."""
    return resolve_data_directory(settings) / PROJECTS_DIRECTORY_NAME


def _read_data_directory_from_environment() -> Path | None:
    """Return `CLAUDE_CONFIG_DIR` when set; None otherwise."""
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    if not configured:
        return None
    directory = Path(configured).expanduser()
    logger.info("claude config dir from environment: %s", directory)
    return directory


def platform_default_data_directory() -> Path:
    """Return the documented default data directory for the current platform."""
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "claude"
        return Path.home() / "AppData" / "Local" / "claude"
    return Path.home() / ".claude"
