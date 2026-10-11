"""Read-only snapshot of Cline CLI's session index database.

Cline keeps `sessions.db` open in WAL mode while it runs, so opening the live
file directly risks `database is locked` and risks writing to a file we
promised never to touch. Instead we open the live file read-only, ask
SQLite's backup API for a consistent private copy in a temp directory, read
that, and delete it — the same contract as the OpenCode snapshot module.

Message files (`*.messages.json`) need no snapshot: they are read with a
single read-only file read, and a torn read surfaces as JSON they fail to
parse, which the reader logs and skips rather than half-counting.
"""

import logging
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from errors.exceptions import CollectorSourceUnreadableError

logger = logging.getLogger(__name__)


@contextmanager
def snapshot_database(source_path: Path) -> Iterator[Path]:
    """Yield a temporary, consistent copy of the session index, then delete it."""
    temporary_directory = Path(tempfile.mkdtemp(prefix="tokenly-cline-"))
    snapshot_path = temporary_directory / source_path.name
    try:
        _copy_database(source_path, snapshot_path)
        yield snapshot_path
    finally:
        _remove_snapshot(temporary_directory)


def _copy_database(source_path: Path, snapshot_path: Path) -> None:
    """Copy the live index into a private file using SQLite's online backup API."""
    try:
        with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
            with sqlite3.connect(snapshot_path) as destination:
                source.backup(destination)
    except sqlite3.Error as error:
        raise CollectorSourceUnreadableError(str(source_path), error) from error
    logger.debug("snapshotted %s to %s", source_path, snapshot_path)


def _remove_snapshot(temporary_directory: Path) -> None:
    """Delete the snapshot directory, logging rather than raising if cleanup fails."""
    try:
        for leftover in temporary_directory.iterdir():
            leftover.unlink(missing_ok=True)
        temporary_directory.rmdir()
    except OSError as error:
        logger.warning("could not remove snapshot directory %s: %s", temporary_directory, error)
