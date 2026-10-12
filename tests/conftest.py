"""Shared test fixtures: an app wired to a temporary SQLite database."""

import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from collectors.opencode.snapshot import _remove_snapshot
from config.settings import Settings
from main import create_app

# A leaked OpenCode snapshot is a full copy of the source database — ~277 MB on a
# real machine. A handful of unclosed collectors is enough to fill a small temp
# filesystem mid-run, which surfaces as a bewildering "database or disk is full"
# hundreds of tests later. So each test cleans up after itself, and the run fails if
# anything actually had to be cleaned up.
SNAPSHOT_GLOB = "tokenly-opencode-*"
_leaks: list[tuple[str, list[str]]] = []


def _snapshots() -> set[Path]:
    return set(Path(tempfile.gettempdir()).glob(SNAPSHOT_GLOB))


@pytest.fixture(autouse=True)
def no_leaked_snapshots(request: pytest.FixtureRequest) -> Iterator[None]:
    """Remove any snapshot copy a test left behind, and remember that it did.

    Cleanup is per test rather than per session on purpose: waiting for the end would
    let a leak fill the temp filesystem before anything noticed. Only directories that
    appeared during this test are touched, so a copy belonging to a longer-lived
    fixture is never removed out from under it.

    The test itself is not failed here. An exception raised during teardown is
    reported by pytest as an error rather than a failure, which reads as though the
    test passed and the cleanup broke. `pytest_sessionfinish` reports the leaks
    together and fails the run instead.
    """
    before = _snapshots()
    yield
    leaked = sorted(str(path) for path in _snapshots() - before)
    for path in leaked:
        _remove_snapshot(Path(path))
    if leaked:
        _leaks.append((request.node.nodeid, leaked))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the run if any test stranded a snapshot copy, naming every one."""
    if not _leaks:
        return
    print("\n" + "=" * 72)
    print(f"{len(_leaks)} test(s) left an OpenCode snapshot copy behind.")
    print("Each is a full copy of the OpenCode database, so a few of them fill the")
    print("temp filesystem. Close the collector, or let the cache be collected.")
    for nodeid, paths in _leaks:
        print(f"\n  {nodeid}")
        for path in paths:
            print(f"      {path}")
    print("=" * 72)
    session.exitstatus = 1


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings for an app that collects nothing unless a test asks it to.

    Automatic collection is off because these tests are about the API, not about
    scanning: leaving it on would read the developer's real OpenCode and Cline
    stores into a throwaway database on every test. The scheduler and the
    coordinator are exercised directly in `test_sync_coordinator.py` and
    `test_sync_scheduler.py`.
    """
    return Settings(
        database_path=tmp_path / "test.db",
        log_level="WARNING",
        sync_enabled=False,
    )


@pytest.fixture
def app(test_settings: Settings) -> Iterator[FastAPI]:
    """An application instance with a throwaway database and no background sync."""
    application = create_app(test_settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Test client for the temporary application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_for_origins(
    tmp_path: Path,
) -> Iterator[Callable[[list[str]], TestClient]]:
    """Build a client whose app allows exactly the given CORS origins.

    The default allowlist is empty, so a test that cares about cross-origin access
    has to opt in explicitly rather than inherit an origin nobody serves from.
    """
    applications: list[FastAPI] = []
    clients: list[TestClient] = []

    def build(origins: list[str]) -> TestClient:
        application = create_app(
            Settings(
                database_path=tmp_path / f"cors-{len(applications)}.db",
                cors_allow_origins=origins,
                log_level="WARNING",
                sync_enabled=False,
            )
        )
        applications.append(application)
        test_client = TestClient(application)
        test_client.__enter__()
        clients.append(test_client)
        return test_client

    yield build

    for test_client, application in zip(clients, applications, strict=True):
        test_client.__exit__(None, None, None)
        application.state.engine.dispose()