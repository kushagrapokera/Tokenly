"""Tests for reusing a database copy while the source has not changed.

Copying the live database is what makes reading it safe, so skipping the copy is the
one place a stale read could hide new usage. These tests pin the rule that decides:
a copy is reused only while the source looks exactly as it did when it was taken.

The write-ahead log case is the important one. OpenCode runs in WAL mode, so new
messages are committed to `opencode.db-wal` and can leave the main file's size and
modification time untouched. Fingerprinting only the main file would reuse a copy
that was missing the very usage it was asked to find.

The tests at the end cover giving the copy back, which is a correctness matter in its
own right: a copy is the full size of the source, so copies that outlive their owner
fill the temp filesystem long before anyone notices.
"""

import gc
import os
import sqlite3
import time
from pathlib import Path

import pytest

from collectors.opencode.snapshot import (
    SnapshotCache,
    SourceState,
    _process_is_running,
    _sweep_abandoned_snapshots,
    snapshot_database,
)


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


# --- giving the copy back ---


def unused_pid() -> int:
    """Return a pid that is not in use, standing in for a process that has died."""
    for candidate in range(40000, 40200):
        if not _process_is_running(candidate):
            return candidate
    raise AssertionError("could not find an unused pid to test with")


def fake_cache_directory(root: Path, pid: int) -> Path:
    """Create a directory named the way a snapshot copy is, owned by the given pid."""
    directory = root / f"tokenly-opencode-cache-{pid}-fake"
    directory.mkdir()
    (directory / "opencode.db").write_bytes(b"not really a database")
    return directory


def test_a_dropped_cache_reclaims_its_copy_without_closing(opencode_db: Path) -> None:
    # An owner that is simply forgotten must not strand a copy of the database.
    cache = SnapshotCache()

    with cache.snapshot(opencode_db) as snapshot_path:
        directory = snapshot_path.parent
        assert directory.is_dir()

    del cache
    gc.collect()

    assert not directory.is_dir()


def test_the_sweep_removes_a_copy_whose_owner_has_died(tmp_path: Path) -> None:
    abandoned = fake_cache_directory(tmp_path, unused_pid())

    removed = _sweep_abandoned_snapshots(tmp_path)

    assert abandoned in removed
    assert not abandoned.is_dir()


def test_the_sweep_never_touches_a_copy_a_live_process_is_using(tmp_path: Path) -> None:
    # Deleting a live copy would pull the database out from under a running scan, so
    # the sweep has to be sure the owner is gone before it acts.
    in_use = fake_cache_directory(tmp_path, os.getpid())

    _sweep_abandoned_snapshots(tmp_path)

    assert in_use.is_dir()


def test_the_sweep_leaves_a_directory_that_names_no_owner(tmp_path: Path) -> None:
    # A directory without a pid belongs to some other version of this code. Guessing
    # at its owner is not worth the risk of deleting a live read.
    unknown = tmp_path / "tokenly-opencode-cache-no-pid-here"
    unknown.mkdir()

    _sweep_abandoned_snapshots(tmp_path)

    assert unknown.is_dir()


def test_closing_a_collector_leaves_no_copy_behind(opencode_db: Path, tmp_path: Path) -> None:
    # The end-to-end guarantee: closing the collector is enough, whatever the caller
    # forgets to do afterwards.
    from collectors.opencode import OpenCodeCollector
    from config.settings import Settings

    collector = OpenCodeCollector(Settings(opencode_data_dir=str(tmp_path)))
    with collector._snapshots.snapshot(opencode_db) as snapshot_path:
        directory = snapshot_path.parent
        assert directory.is_dir()

    collector.close()

    assert not directory.is_dir()
