"""Tests for caching OpenCode's data directory instead of re-asking the CLI.

Asking costs about 600 ms — the CLI has to start and print its paths — and the
answer only changes when the user edits OpenCode's own configuration. Re-asking
on every scan spent 71% of a scan rediscovering a directory.

These tests pin the four rules that make caching safe rather than merely fast:
successes only, per collector instance, self-healing when the path goes stale,
and an explicit way out for a manual rescan.
"""

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from collectors.opencode import OpenCodeCollector
from collectors.opencode.locator import DataDirectoryResolver
from config.settings import Settings
from tests.collectors.opencode.conftest import OpenCodeDatabaseBuilder

CLI_OUTPUT = "home  /home/dev\ndata  {directory}\nbin   /bin\n"


def answer_with(monkeypatch: pytest.MonkeyPatch, directory: Path | None) -> list[list[str]]:
    """Make the CLI answer with `directory`, counting how often it was asked.

    Returns the list of commands seen, so a test can assert the CLI was asked
    once rather than once per scan.
    """
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        if directory is None:
            return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr="no")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=CLI_OUTPUT.format(directory=directory),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


@pytest.fixture
def opencode_store(tmp_path: Path) -> Iterator[Path]:
    """A directory that looks like a resolved OpenCode data directory."""
    data_dir = tmp_path / "opencode-data"
    data_dir.mkdir()
    (data_dir / "opencode.db").write_bytes(b"")
    yield data_dir


def test_the_cli_is_asked_once_however_many_times_the_path_is_resolved(
    monkeypatch: pytest.MonkeyPatch,
    opencode_store: Path,
) -> None:
    calls = answer_with(monkeypatch, opencode_store)
    resolver = DataDirectoryResolver(Settings())

    for _ in range(5):
        assert resolver.data_directory() == opencode_store

    assert len(calls) == 1


def test_repeated_scans_do_not_re_ask_the_cli(
    monkeypatch: pytest.MonkeyPatch,
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    # The end-to-end claim: a collector scanning several times over a real store
    # asks the CLI exactly once. Before this, every scan paid ~600 ms for it.
    calls = answer_with(monkeypatch, opencode_db.path.parent)
    collector = OpenCodeCollector(Settings(log_level="WARNING"))

    for _ in range(3):
        result = collector.discover()

    assert result.available is True
    assert len(calls) == 1


def test_a_manual_rescan_asks_the_cli_again(
    monkeypatch: pytest.MonkeyPatch,
    opencode_db: OpenCodeDatabaseBuilder,
) -> None:
    # The escape hatch: pressing rescan must produce a genuine second look.
    calls = answer_with(monkeypatch, opencode_db.path.parent)
    collector = OpenCodeCollector(Settings(log_level="WARNING"))
    collector.discover()

    collector.refresh()
    collector.discover()

    assert len(calls) == 2


def test_an_explicit_setting_never_consults_the_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = answer_with(monkeypatch, tmp_path)
    settings = Settings(opencode_data_dir=tmp_path, log_level="WARNING")

    collector = OpenCodeCollector(settings)
    collector.discover()
    collector.refresh()
    collector.discover()

    assert calls == []


def test_a_failed_probe_is_not_cached(
    monkeypatch: pytest.MonkeyPatch,
    opencode_store: Path,
) -> None:
    # Installing OpenCode later must be noticed on the next scan, so a probe that
    # failed must never be remembered as "there is no data directory".
    answer_with(monkeypatch, None)
    resolver = DataDirectoryResolver(Settings())

    first = resolver.data_directory()

    answer_with(monkeypatch, opencode_store)
    second = resolver.data_directory()

    assert first != second
    assert second == opencode_store


def test_a_cached_path_that_lost_its_database_is_re_resolved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # The self-healing rule: the user moved their data directory. The old path no
    # longer holds opencode.db, so the CLI is asked again rather than trusting a
    # cache that has gone stale.
    old_directory = tmp_path / "old-data"
    old_directory.mkdir()
    (old_directory / "opencode.db").write_bytes(b"")
    new_directory = tmp_path / "new-data"
    new_directory.mkdir()
    (new_directory / "opencode.db").write_bytes(b"")

    answer_with(monkeypatch, old_directory)
    resolver = DataDirectoryResolver(Settings())
    assert resolver.database_path() == old_directory / "opencode.db"

    # The user moves it: the old path keeps existing but no longer holds the db.
    (old_directory / "opencode.db").unlink()
    answer_with(monkeypatch, new_directory)

    assert resolver.database_path() == new_directory / "opencode.db"


def test_refresh_makes_the_next_call_ask_again(
    monkeypatch: pytest.MonkeyPatch,
    opencode_store: Path,
) -> None:
    # The escape hatch: a manual rescan must not be answered from the cache.
    calls = answer_with(monkeypatch, opencode_store)
    resolver = DataDirectoryResolver(Settings())
    resolver.data_directory()

    resolver.invalidate()
    resolver.data_directory()

    assert len(calls) == 2


def test_two_collectors_never_share_a_cached_answer(
    monkeypatch: pytest.MonkeyPatch,
    opencode_store: Path,
) -> None:
    # The cache is per instance on purpose: a module-level one would let one
    # collector's answer leak into another's, and across tests.
    answer_with(monkeypatch, opencode_store)

    first = DataDirectoryResolver(Settings())
    second = DataDirectoryResolver(Settings())

    assert first.data_directory() == second.data_directory() == opencode_store
    assert first._cached_directory is not second._cached_directory  # noqa: SLF001


def test_module_level_resolution_still_asks_every_time(
    monkeypatch: pytest.MonkeyPatch,
    opencode_store: Path,
) -> None:
    # Scripts and the locator's own tests rely on a fresh answer per call; caching
    # is the resolver's job, not the function's.
    from collectors.opencode.locator import resolve_data_directory

    calls = answer_with(monkeypatch, opencode_store)

    resolve_data_directory(Settings())
    resolve_data_directory(Settings())

    assert len(calls) == 2