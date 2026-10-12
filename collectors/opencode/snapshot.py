"""Read-only snapshot of OpenCode's live SQLite database.

OpenCode keeps its database open in WAL mode while it runs, so opening the live file
directly risks `database is locked` and risks writing to a file we promised never to
touch. Instead we open the live file read-only, ask SQLite's backup API for a
consistent private copy in a temp directory, read that, and delete it.

The live file is opened with `mode=ro` so SQLite itself refuses any write, and the
snapshot lives outside OpenCode's data directory so it is never mistaken for source data.

`SnapshotCache` keeps that copy between scans while the source is unchanged, which is
worth ~172 ms per scan. Copying is what makes reading safe, so the decision to skip it
is the one place a stale read could hide new usage — the fingerprint below is
deliberately paranoid about that, and §A2 of `docs/parallelism.md` records the trade-off.

That caching is also why this module is careful about giving the copy back. Each copy
is the full size of the source database, so copies that outlive their owner would fill
a temp filesystem: one collector per test adds up to gigabytes over a test run. Three
things prevent that, and all three are needed because each covers a case the others miss:

1. `close()` deletes the copy deterministically, so an owner that behaves leaves
   nothing behind.
2. A `weakref.finalize` deletes it when the cache is garbage collected, which covers an
   owner that is simply dropped without being closed.
3. `atexit` (which `weakref.finalize` registers by default) covers a clean exit, and the
   pid in the directory name lets a later run sweep up after a process that died
   without any of the above — a kill, a crash, or a power cut.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from errors.exceptions import CollectorSourceUnreadableError

logger = logging.getLogger(__name__)

WAL_SUFFIX = "-wal"

# The owning pid is part of the directory name so an abandoned copy can be identified
# as abandoned. Without it, a killed process leaves a directory that no later run can
# tell apart from one a live server is still reading from.
CACHE_PREFIX = f"tokenly-opencode-cache-{os.getpid()}-"
CACHE_PREFIX_PATTERN = "tokenly-opencode-cache-"
SNAPSHOT_PREFIX = "tokenly-opencode-"


@contextmanager
def snapshot_database(source_path: Path) -> Iterator[Path]:
    """Yield a temporary, consistent copy of the OpenCode database, then delete it."""
    temporary_directory = Path(tempfile.mkdtemp(prefix=SNAPSHOT_PREFIX))
    snapshot_path = temporary_directory / source_path.name
    try:
        _copy_database(source_path, snapshot_path)
        yield snapshot_path
    finally:
        _remove_snapshot(temporary_directory)


@dataclass(frozen=True)
class SourceState:
    """Everything about a source that tells whether a copy of it is still current.

    The write-ahead log is part of this on purpose. OpenCode runs in WAL mode, so new
    messages are committed to `opencode.db-wal` and may leave the main file's size and
    modification time completely unchanged. Fingerprinting the main file alone would
    therefore reuse a snapshot that was missing the very usage it was asked to find.
    The `-shm` file is deliberately excluded: it is a shared-memory index whose
    timestamp moves without any data changing.
    """

    main: tuple[int, int] | None
    wal: tuple[int, int] | None

    @classmethod
    def of(cls, source_path: Path) -> SourceState:
        """Read the current state of a database and its write-ahead log."""
        return cls(main=_stat(source_path), wal=_stat(_wal_path(source_path)))


@dataclass(frozen=True)
class _CachedSnapshot:
    """One copied database, and the source state it was copied from."""

    path: Path
    state: SourceState


class SnapshotCache:
    """Reuses one copy of a database while the source has not changed.

    Correctness rests on `SourceState`: a copy is reused only when the source still
    looks exactly as it did when the copy was made. If that ever lies — a change that
    does not move either fingerprint — the consequence is bounded. The reused copy is
    simply older, so the scan finds nothing new, and the scan after it copies again and
    catches up. Usage is delayed, never skipped: the checkpoint only advances over
    timestamps the scan actually read.
    """

    def __init__(self, prefix: str = CACHE_PREFIX) -> None:
        self._prefix = prefix
        self._cached: _CachedSnapshot | None = None
        # Two requests can scan the same collector at once (the background scheduler
        # and a status view). Only one should be copying; readers of a shared snapshot
        # need no lock, since SQLite allows concurrent readers of one file.
        self._lock = threading.Lock()
        _sweep_abandoned_snapshots()

    @contextmanager
    def snapshot(self, source_path: Path) -> Iterator[Path]:
        """Yield a current copy of the database, copying only if it has changed."""
        with self._lock:
            entry = self._entry_for(source_path)
        try:
            yield entry.path
        finally:
            # The copy outlives this scan on purpose; that is the whole point of caching.
            pass

    def close(self) -> None:
        """Delete the cached copy and forget it."""
        with self._lock:
            cached = self._cached
            self._cached = None
        if cached is None:
            return
        _remove_snapshot(cached.path.parent)
        logger.debug("discarded the cached opencode snapshot")

    def _entry_for(self, source_path: Path) -> _CachedSnapshot:
        """Return a usable copy of the source, reusing the cached one if it is current."""
        state = SourceState.of(source_path)
        cached = self._cached
        if cached is not None and cached.state == state and cached.path.is_file():
            logger.debug("reusing the opencode snapshot; source unchanged since %s", state.main)
            return cached

        if cached is not None:
            logger.info("opencode database changed; taking a fresh snapshot")
            _remove_snapshot(cached.path.parent)

        snapshot_path = self._copy_into_temporary_directory(source_path)
        self._cached = _CachedSnapshot(path=snapshot_path, state=state)
        return self._cached

    def _copy_into_temporary_directory(self, source_path: Path) -> Path:
        """Copy the source into a temp directory tied to this cache's lifetime.

        The finalizer covers the three ways a copy can stop being wanted: an explicit
        `close()`, the cache being garbage collected, and a normal interpreter exit
        (which `weakref.finalize` registers for by default). It does not cover a kill
        or a crash, which is what `_sweep_abandoned_snapshots` is for.
        """
        temporary_directory = Path(tempfile.mkdtemp(prefix=self._prefix))
        weakref.finalize(self, _remove_snapshot, temporary_directory)
        snapshot_path = temporary_directory / source_path.name
        _copy_database(source_path, snapshot_path)
        return snapshot_path


def _sweep_abandoned_snapshots(directory: Path | None = None) -> list[Path]:
    """Delete cached copies left behind by processes that are no longer running.

    Only directories naming a dead owner are removed, so a concurrently running
    server's copy is never touched. A directory whose name carries no pid is left
    alone too: it belongs to some other version of this code, and guessing at its
    owner is not worth the risk of deleting a live read.

    Returns the directories it removed, so a caller can report them.
    """
    root = Path(directory) if directory is not None else Path(tempfile.gettempdir())
    removed: list[Path] = []
    try:
        candidates = list(root.glob(f"{CACHE_PREFIX_PATTERN}*"))
    except OSError as error:
        logger.warning("could not list %s for abandoned snapshots: %s", root, error)
        return removed

    for candidate in candidates:
        owner = _owning_pid(candidate.name)
        if owner is None or _process_is_running(owner):
            continue
        _remove_snapshot(candidate)
        removed.append(candidate)

    if removed:
        logger.info("removed %d abandoned opencode snapshot(s) from earlier runs", len(removed))
    return removed


def _owning_pid(directory_name: str) -> int | None:
    """Return the pid named in a cache directory, or None when it names no owner."""
    if not directory_name.startswith(CACHE_PREFIX_PATTERN):
        return None
    remainder = directory_name[len(CACHE_PREFIX_PATTERN) :]
    # The pid is followed by the separator mkdtemp appends before its random suffix.
    digits, separator, _ = remainder.partition("-")
    if not separator or not digits.isdigit():
        return None
    return int(digits)


def _process_is_running(pid: int) -> bool:
    """Report whether a pid is still alive.

    Signal 0 performs the permission and existence checks without delivering
    anything. A `PermissionError` means the process exists but belongs to someone
    else, which still counts as running.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        logger.warning("could not check whether pid %d is alive: %s", pid, error)
        return True
    return True


def _wal_path(source_path: Path) -> Path:
    """Return the write-ahead log that sits beside a SQLite database."""
    return source_path.with_name(source_path.name + WAL_SUFFIX)


def _stat(path: Path) -> tuple[int, int] | None:
    """Return a file's size and modification time, or None when it is not there."""
    try:
        status = path.stat()
    except OSError:
        return None
    return status.st_size, status.st_mtime_ns


def _copy_database(source_path: Path, snapshot_path: Path) -> None:
    """Copy the live database into a private file using SQLite's online backup API."""
    try:
        with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
            with sqlite3.connect(snapshot_path) as destination:
                source.backup(destination)
    except sqlite3.Error as error:
        raise CollectorSourceUnreadableError(str(source_path), error) from error
    logger.debug("snapshotted %s to %s", source_path, snapshot_path)


def _remove_snapshot(temporary_directory: Path) -> None:
    """Delete the snapshot directory, logging rather than raising if cleanup fails.

    Idempotent, because a directory can be asked to disappear more than once: a cached
    copy is removed when it is replaced or when the collector closes, and the same
    directory also has a handler registered for process exit.
    """
    if not temporary_directory.is_dir():
        return
    try:
        for leftover in temporary_directory.iterdir():
            leftover.unlink(missing_ok=True)
        temporary_directory.rmdir()
    except OSError as error:
        logger.warning("could not remove snapshot directory %s: %s", temporary_directory, error)