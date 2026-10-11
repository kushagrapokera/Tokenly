"""Tests for reusing a database copy while the source has not changed.

Copying the live database is what makes reading it safe, so skipping the copy is the
one place a stale read could hide new usage. These tests pin the rule that decides:
a copy is reused only while the source looks exactly as it did when it was taken.

The write-ahead log case is the important one. OpenCode runs in WAL mode, so new
messages are committed to `opencode.db-wal` and can leave the main file's size and
modification time untouched. Fingerprinting only the main file would reuse a copy
that was missing the very usage it was asked to find.
"""

import os
import sqlite3
import time
from pathlib import Path

import pytest

from collectors.opencode.snapshot import SnapshotCache, SourceState, snapshot_database


@pytest.fixture
def opencode_db(tmp_path: Path) -> Path:
    """A minimal SQLite database with the tables a snapshot has to carry."""
    path = tmp_path / "opencode.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE session (id TEXT PRIMARY KEY, time_created INTEGER)")
        connection.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT)")
        connection.execute("INSERT INTO session VALUES ('ses_1', 1)")
    return path


def write_wal(database_path: Path, size: int) -> Path:
    """Create or extend the write-ahead log beside a database."""
    wal_path = database_path.with_name(database_path.name + "-wal")
    wal_path.write_bytes(b"x" * size)
    return wal_path


def rows_in(snapshot_path: Path) -> int:
    """Count the sessions visible in a database file."""
    with sqlite3.connect(snapshot_path) as connection:
        return int(connection.execute("SELECT count(*) FROM session").fetchone()[0])


def test_an_unchanged_source_is_copied_only_once(opencode_db: Path) -> None:
    cache = SnapshotCache()

    with cache.snapshot(opencode_db) as first:
        with cache.snapshot(opencode_db) as second:
            assert first == second

    cache.close()


def test_a_changed_source_produces_a_new_copy(opencode_db: Path) -> None:
    cache = SnapshotCache()

    with cache.snapshot(opencode_db) as first:
        with sqlite3.connect(opencode_db) as connection:
            connection.execute("INSERT INTO session VALUES ('ses_2', 2)")
        time.sleep(0.01)
        with cache.snapshot(opencode_db) as second:
            assert second != first
            # The new copy really does contain the row added since the first.
            assert rows_in(second) == 2


def test_a_write_in_the_write_ahead_log_invalidates_the_copy(opencode_db: Path) -> None:
    # The case that would lose usage if the log were ignored: the main file is
    # untouched, so its size and timestamp still match, but the data is new.
    cache = SnapshotCache()

    with cache.snapshot(opencode_db) as first:
        write_wal(opencode_db, 512)

        with cache.snapshot(opencode_db) as second:
            assert second != first


def test_a_shrinking_write_ahead_log_also_invalidates(opencode_db: Path) -> None:
    # A checkpoint folds the log back into the main file and truncates it. Same size
    # must not be assumed; the timestamp is part of the fingerprint for that reason.
    cache = SnapshotCache()
    write_wal(opencode_db, 4096)

    with cache.snapshot(opencode_db) as first:
        write_wal(opencode_db, 4096)
        _set_mtime(opencode_db.with_name(opencode_db.name + "-wal"))

        with cache.snapshot(opencode_db) as second:
            assert second != first


def _set_mtime(path: Path) -> None:
    """Move a file's modification time forward without changing its size."""
    status = path.stat()
    os.utime(path, ns=(status.st_atime_ns, status.st_mtime_ns + 1_000_000))


def test_the_source_state_notices_a_removed_write_ahead_log(opencode_db: Path) -> None:
    wal = write_wal(opencode_db, 256)
    with_wal = SourceState.of(opencode_db)

    wal.unlink()
    without_wal = SourceState.of(opencode_db)

    assert with_wal != without_wal


def test_a_missing_database_does_not_raise(opencode_db: Path) -> None:
    # Absence is a normal state, not an error: the collector reports "not installed".
    state = SourceState.of(opencode_db.with_name("nothing-here.db"))

    assert state.main is None


def test_two_caches_do_not_share_a_copy(opencode_db: Path) -> None:
    first = SnapshotCache()
    second = SnapshotCache()

    with first.snapshot(opencode_db) as first_path:
        with second.snapshot(opencode_db) as second_path:
            assert first_path != second_path

    first.close()
    second.close()


def test_closing_discards_the_cached_copy(opencode_db: Path) -> None:
    cache = SnapshotCache()

    with cache.snapshot(opencode_db) as snapshot_path:
        cache.close()
        assert not snapshot_path.parent.is_dir()

    # And a later snapshot still works, copying afresh.
    with cache.snapshot(opencode_db) as again:
        assert rows_in(again) == 1
    cache.close()


def test_the_one_shot_helper_still_deletes_its_copy(opencode_db: Path) -> None:
    # `snapshot_database` is unchanged by all of this: scripts and tests rely on it
    # leaving nothing behind.
    with snapshot_database(opencode_db) as snapshot_path:
        directory = snapshot_path.parent
        assert rows_in(snapshot_path) == 1

    assert not directory.is_dir()


def test_a_snapshot_is_a_faithful_copy(opencode_db: Path) -> None:
    # A cached copy is still a real, complete database, not a partial file.
    cache = SnapshotCache()

    with cache.snapshot(opencode_db) as snapshot_path:
        with sqlite3.connect(snapshot_path) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            sessions = connection.execute("SELECT count(*) FROM session").fetchone()[0]

    assert integrity == "ok"
    assert sessions == 1
    cache.close()