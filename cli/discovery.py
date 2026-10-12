"""Auto-discovery of each assistant's data directory, cross-platform.

A fresh clone should need no setup: `myusage` finds where OpenCode, Cline, Claude
Code, and Codex CLI keep their data on the current machine, remembers it in a
small JSON config, and feeds the paths to `Settings`. Nothing here is OS-specific
except the per-OS default/config-directory lookups, which are centralized here and
covered by simulated-OS tests.

Resolution order per platform: saved config -> environment variable -> platform
default -> a bounded filesystem search for the platform's signature. Every
filesystem touch is wrapped so a permission error (Windows ACLs, macOS TCC) skips
an entry rather than aborting discovery.
"""

import json
import logging
import os
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

from collectors.claude.locator import (
    CLAUDE_CONFIG_ENV_VAR,
    PROJECTS_DIRECTORY_NAME,
)
from collectors.claude.locator import platform_default_data_directory as claude_default
from collectors.cline.locator import SESSIONS_DATABASE_FILE_NAME
from collectors.cline.locator import SESSIONS_DIRECTORY_NAME as CLINE_SESSIONS_DIR
from collectors.cline.locator import platform_default_data_directory as cline_default
from collectors.codex.locator import (
    CODEX_HOME_ENV_VAR,
)
from collectors.codex.locator import SESSIONS_DIRECTORY_NAME as CODEX_SESSIONS_DIR
from collectors.codex.locator import platform_default_home_directory as codex_default
from collectors.codex.reader import ROLLOUT_GLOB
from collectors.opencode.locator import DATABASE_FILE_NAME as OPENCODE_DB_FILE
from collectors.opencode.locator import platform_default_data_directory as opencode_default

logger = logging.getLogger(__name__)

CONFIG_FILE_NAME = "config.json"

# Directories never worth descending into during a search (matched case-insensitively,
# since names can differ in case across filesystems).
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "library",
        "appdata",
        "__pycache__",
        ".cache",
        ".npm",
        ".cargo",
        ".rustup",
        "dist",
        "build",
    }
)

# Bounds that keep the search fast and predictable (see docs/cli-plan.md §7).
MAX_DEPTH = 6
MAX_VISITED = 20_000
BUDGET_SECONDS = 4.0


@dataclass(frozen=True)
class DiscoveredPaths:
    """The data directories discovery resolved, one per platform (None if absent)."""

    codex_home: Path | None = None
    claude_data_dir: Path | None = None
    cline_data_dir: Path | None = None
    opencode_data_dir: Path | None = None


# --- config file location, cross-platform ---


def config_dir_for(os_name: str, platform: str, env: dict[str, str], home: Path) -> Path:
    """Return Tokenly's config directory for the given OS facts.

    Pure and OS-fact-driven so every platform's behavior is unit-tested on any
    host. `user_config_dir` calls this with the real runtime values.
    """
    if os_name == "nt":
        base = env.get("APPDATA")
        root = Path(base) if base else home / "AppData" / "Roaming"
    elif platform == "darwin":
        root = home / "Library" / "Application Support"
    else:
        base = env.get("XDG_CONFIG_HOME")
        root = Path(base) if base else home / ".config"
    return root / "tokenly"


def user_config_dir() -> Path:
    """Return Tokenly's per-user config directory for the current OS."""
    return config_dir_for(os.name, sys.platform, dict(os.environ), Path.home())


def config_path() -> Path:
    """Return the full path of the saved config file."""
    return user_config_dir() / CONFIG_FILE_NAME


def load_config() -> dict[str, str]:
    """Read the saved config, returning an empty mapping when absent or invalid."""
    path = config_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("config at %s is not valid JSON; ignoring it", path)
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if isinstance(value, str)}


def save_config(paths: DiscoveredPaths) -> None:
    """Persist the discovered paths, creating the config directory if needed."""
    payload = {key: str(value) for key, value in asdict(paths).items() if value is not None}
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        logger.warning("could not write config to %s: %s", path, error)
        return
    logger.info("saved discovered paths to %s", path)


# --- bounded filesystem search ---


def _search_roots() -> list[Path]:
    """Return the directories a search starts from: common project roots plus home."""
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Documents",
        home / "Projects",
        home / "source",
        home / "repos",
        home / "code",
        home / "dev",
        home / "workspace",
        home,
    ]
    roots: list[Path] = []
    for candidate in candidates:
        try:
            if candidate.is_dir():
                roots.append(candidate)
        except OSError:
            continue
    return roots


def _iter_directories(roots: list[Path]):
    """Yield directories breadth-first, bounded by depth, count, time, and a skip-list.

    Each directory is yielded at most once even when reachable from several roots.
    A directory that cannot be read is skipped, never fatal.
    """
    deadline = time.monotonic() + BUDGET_SECONDS
    seen: set[Path] = set()
    visited = 0
    queue: deque[tuple[Path, int]] = deque((root, 0) for root in roots)
    while queue:
        if visited >= MAX_VISITED or time.monotonic() > deadline:
            logger.debug("search stopped after visiting %d directories", visited)
            return
        directory, depth = queue.popleft()
        try:
            resolved = directory.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        visited += 1
        yield directory
        if depth >= MAX_DEPTH:
            continue
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue
            if child.name.lower() in SKIP_DIR_NAMES:
                continue
            queue.append((child, depth + 1))


def _search(probe) -> Path | None:
    """Run a bounded search, returning the first directory `probe` claims."""
    for directory in _iter_directories(_search_roots()):
        try:
            found = probe(directory)
        except OSError:
            continue
        if found is not None:
            return found
    return None


# --- per-platform probes (a directory -> its resolved home, or None) ---


def _has_rollout(sessions_dir: Path) -> bool:
    """Report whether a `sessions` directory holds any rollout file within depth 4."""
    try:
        for path in sessions_dir.rglob(ROLLOUT_GLOB):
            try:
                if len(path.relative_to(sessions_dir).parts) <= 4:
                    return True
            except ValueError:
                continue
    except OSError:
        return False
    return False


def _probe_codex(directory: Path) -> Path | None:
    if directory.name == CODEX_SESSIONS_DIR and _has_rollout(directory):
        return directory.parent
    return None


def _probe_claude(directory: Path) -> Path | None:
    if directory.name != PROJECTS_DIRECTORY_NAME:
        return None
    try:
        # Claude stores sessions at projects/<project>/<session>.jsonl (two levels).
        if any(directory.glob("*/*.jsonl")):
            return directory.parent
    except OSError:
        return None
    return None


def _probe_cline(directory: Path) -> Path | None:
    try:
        if (directory / CLINE_SESSIONS_DIR).is_dir() and (
            directory / "db" / SESSIONS_DATABASE_FILE_NAME
        ).is_file():
            return directory
    except OSError:
        return None
    return None


def _probe_opencode(directory: Path) -> Path | None:
    try:
        if (directory / OPENCODE_DB_FILE).is_file():
            return directory
    except OSError:
        return None
    return None


# --- per-platform validators ---


def _valid_codex(home: Path) -> bool:
    try:
        sessions = home / CODEX_SESSIONS_DIR
        return sessions.is_dir() and _has_rollout(sessions)
    except OSError:
        return False


def _valid_claude(data_dir: Path) -> bool:
    try:
        projects = data_dir / PROJECTS_DIRECTORY_NAME
        # Sessions live at projects/<project>/<session>.jsonl (two levels deep).
        return projects.is_dir() and any(projects.glob("*/*.jsonl"))
    except OSError:
        return False


def _valid_cline(data_dir: Path) -> bool:
    try:
        return (data_dir / "db" / SESSIONS_DATABASE_FILE_NAME).is_file()
    except OSError:
        return False


def _valid_opencode(data_dir: Path) -> bool:
    try:
        return (data_dir / OPENCODE_DB_FILE).is_file()
    except OSError:
        return False


# --- per-platform discovery: config -> env -> default -> search ---


def _from_config(config: dict[str, str], key: str, validator) -> Path | None:
    """Return the saved path for `key` when it still validates, else None."""
    saved = config.get(key)
    if not saved:
        return None
    candidate = Path(saved).expanduser()
    return candidate if validator(candidate) else None


def discover_codex_home(config: dict[str, str], force: bool) -> Path | None:
    if not force:
        saved = _from_config(config, "codex_home", _valid_codex)
        if saved is not None:
            return saved
    env = os.environ.get(CODEX_HOME_ENV_VAR)
    if env:
        # An explicit setting is user intent; honour it even if currently empty.
        return Path(env).expanduser()
    default = codex_default()
    if _valid_codex(default):
        return default
    return _search(_probe_codex)


def discover_claude_data_dir(config: dict[str, str], force: bool) -> Path | None:
    if not force:
        saved = _from_config(config, "claude_data_dir", _valid_claude)
        if saved is not None:
            return saved
    env = os.environ.get(CLAUDE_CONFIG_ENV_VAR)
    if env:
        return Path(env).expanduser()
    default = claude_default()
    if _valid_claude(default):
        return default
    return _search(_probe_claude)


def discover_cline_data_dir(config: dict[str, str], force: bool) -> Path | None:
    if not force:
        saved = _from_config(config, "cline_data_dir", _valid_cline)
        if saved is not None:
            return saved
    default = cline_default()
    if _valid_cline(default):
        return default
    return _search(_probe_cline)


def discover_opencode_data_dir(config: dict[str, str], force: bool) -> Path | None:
    if not force:
        saved = _from_config(config, "opencode_data_dir", _valid_opencode)
        if saved is not None:
            return saved
    default = opencode_default()
    if _valid_opencode(default):
        return default
    # When nothing is found, return None so the OpenCode collector's own locator
    # (which can ask `opencode debug paths`) still gets a turn at sync time.
    return _search(_probe_opencode)


def discover_paths(force: bool = False) -> DiscoveredPaths:
    """Resolve every platform's data directory and persist the result.

    `force` ignores the saved config and re-runs env/default/search for each.
    """
    config = {} if force else load_config()
    paths = DiscoveredPaths(
        codex_home=discover_codex_home(config, force),
        claude_data_dir=discover_claude_data_dir(config, force),
        cline_data_dir=discover_cline_data_dir(config, force),
        opencode_data_dir=discover_opencode_data_dir(config, force),
    )
    save_config(paths)
    return paths


def build_settings(paths: DiscoveredPaths):
    """Build Settings from discovered paths, with the database under the repo.

    The database path is resolved relative to the installed package, so `myusage`
    works from any working directory.
    """
    from config.settings import Settings

    repo_root = Path(__file__).resolve().parents[1]
    return Settings(
        database_path=repo_root / "data" / "tokenly.db",
        opencode_data_dir=paths.opencode_data_dir,
        cline_data_dir=paths.cline_data_dir,
        claude_data_dir=paths.claude_data_dir,
        codex_home=paths.codex_home,
        log_level="WARNING",
    )


