"""Alembic environment: reads the database URL from application settings."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Importing the models registers them on Base.metadata, which is what autogenerate
# compares the database against. Without this, metadata is empty and every table looks
# like it is missing.
import database.models  # noqa: F401  (imported for its side effect on metadata)
from alembic import context
from config.settings import get_settings
from database.connection import Base

config = context.config

# Alembic's logging setup replaces the root logger's handlers. A caller that has
# already configured logging — the running application, or a test asserting on
# captured log records — passes `configure_logger=False` to keep its own.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

# An explicitly supplied URL wins. The application migrates the database it was
# configured with, which is not necessarily the one `get_settings()` resolves, and
# honouring the override is what keeps that safe. Run from the command line with
# no URL given, this still falls back to the configured database.
config.set_main_option(
    "sqlalchemy.url", config.get_main_option("sqlalchemy.url") or get_settings().database_url
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a database connection, emitting SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
