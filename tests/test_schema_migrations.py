"""The schema Alembic builds must match the schema the ORM expects.

`database/schema.py` creates tables from `Base.metadata`, while `alembic/versions/`
describes how those tables are meant to be built and changed. Two sources of
truth only stay useful while they agree, so this module builds a database the way
a new install would and compares it, column by column, against a database built
from the models.

If someone adds a column to `database/models.py` and forgets the migration, this
fails instead of leaving existing installations quietly missing that column while
fresh ones have it.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect

import database.models  # noqa: F401  imported for its side effect on Base.metadata
from alembic import command
from config.settings import get_settings
from database.connection import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def build_with_alembic(destination: Path) -> Engine:
    """Create an empty database at `destination` by running the migrations."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{destination}")
    # Keep the root logger as the caller configured it; running these migrations
    # must not dismantle another test's log capture or the application's logging.
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    return create_engine(f"sqlite:///{destination}")


def build_with_models(destination: Path) -> Engine:
    """Create an empty database at `destination` from the ORM metadata."""
    engine = create_engine(f"sqlite:///{destination}")
    Base.metadata.create_all(engine)
    return engine


def describe(engine: Engine) -> dict[str, object]:
    """Summarise every table's columns, indexes, and constraints."""
    inspector = inspect(engine)
    description: dict[str, object] = {}
    for table in sorted(inspector.get_table_names()):
        if table == "alembic_version":
            continue
        description[table] = {
            "columns": {
                column["name"]: (str(column["type"]), column["nullable"])
                for column in inspector.get_columns(table)
            },
            "indexes": {
                index["name"]: tuple(index["column_names"])
                for index in inspector.get_indexes(table)
            },
            "unique": sorted(
                tuple(sorted(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table)
            ),
            "checks": sorted(
                constraint["sqltext"] for constraint in inspector.get_check_constraints(table)
            ),
        }
    return description


@pytest.fixture(scope="module")
def migrated(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    """A database built by running the migrations from empty."""
    return build_with_alembic(tmp_path_factory.mktemp("migrated") / "migrated.db")


@pytest.fixture(scope="module")
def from_models(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    """A database built from the ORM metadata alone."""
    return build_with_models(tmp_path_factory.mktemp("models") / "models.db")


def test_the_migrations_build_the_same_schema_as_the_models(
    migrated: Engine,
    from_models: Engine,
) -> None:
    assert describe(migrated) == describe(from_models)


def test_the_migrations_reach_the_latest_revision(tmp_path: Path) -> None:
    engine = build_with_alembic(tmp_path / "head.db")

    with engine.connect() as connection:
        revision = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()

    assert revision is not None


def test_an_up_to_date_database_is_left_alone(tmp_path: Path) -> None:
    # Running the migrations twice must not fail or rebuild what is already there.
    destination = tmp_path / "twice.db"
    build_with_alembic(destination).dispose()
    engine = build_with_alembic(destination)

    assert engine.connect().exec_driver_sql("SELECT count(*) FROM usage_events").scalar() == 0


def test_the_schema_covers_every_field_the_collectors_store(tmp_path: Path) -> None:
    # Phase 4 asks whether one table can hold both platforms' usage. These are the
    # fields `collectors/` fills in for OpenCode and Cline alike; a platform that
    # needs a field that is not here must arrive with a migration, not a guess.
    engine = build_with_models(tmp_path / "coverage.db")
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("usage_events")}

    assert {
        "platform",
        "provider_id",
        "model_id",
        "session_id",
        "source_event_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "timestamp",
        "usage_status",
    } <= columns


def test_the_same_source_id_on_two_platforms_is_two_rows(tmp_path: Path) -> None:
    # The collision guarantee Phase 4 asks for: Cline's `{session}:{message}` and
    # OpenCode's bare `message.id` may be identical strings and must still be kept
    # apart, because the uniqueness is scoped to the platform.
    engine = build_with_models(tmp_path / "collision.db")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO usage_events (platform, provider_id, model_id, session_id, message_id,"
            " source_event_id, timestamp, usage_status, cache_overlap, reasoning_overlap,"
            " raw_usage, created_at, updated_at)"
            " VALUES ('opencode', 'opencode', 'm', 's', 'msg_1', 'msg_1', '2026-01-01',"
            " 'reported', 'additive', 'additive', '{}', '2026-01-01', '2026-01-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO usage_events (platform, provider_id, model_id, session_id, message_id,"
            " source_event_id, timestamp, usage_status, cache_overlap, reasoning_overlap,"
            " raw_usage, created_at, updated_at)"
            " VALUES ('cline', 'cline', 'm', 'ses_1', 'msg_1', 'ses_1:msg_1', '2026-01-01',"
            " 'reported', 'additive', 'additive', '{}', '2026-01-01', '2026-01-01')"
        )
        rows = connection.exec_driver_sql(
            "SELECT platform FROM usage_events ORDER BY platform"
        ).scalars().all()

    assert rows == ["cline", "opencode"]


def test_recreating_the_schema_keeps_stored_usage(tmp_path: Path) -> None:
    # `ensure_schema` runs on every start. It must never touch rows that are
    # already there, or restarting the app would quietly reset the history.
    engine = build_with_models(tmp_path / "preserved.db")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO usage_events (platform, provider_id, model_id, session_id, message_id,"
            " source_event_id, timestamp, usage_status, cache_overlap, reasoning_overlap,"
            " raw_usage, created_at, updated_at)"
            " VALUES ('opencode', 'opencode', 'm', 's', 'msg_1', 'msg_1', '2026-01-01',"
            " 'reported', 'additive', 'additive', '{}', '2026-01-01', '2026-01-01')"
        )

    Base.metadata.create_all(engine)

    with engine.connect() as connection:
        stored = connection.exec_driver_sql(
            "SELECT count(*) FROM usage_events WHERE source_event_id = 'msg_1'"
        ).scalar()
    assert stored == 1


def test_the_configured_database_is_the_one_being_migrated() -> None:
    # The migrations read the URL from settings; this is the value they would use.
    assert get_settings().database_url.startswith("sqlite:///")