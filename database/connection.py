"""SQLite connection handling: engine creation, session factory, and health ping."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from errors.exceptions import DatabaseUnavailableError

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base all ORM models inherit from; migrations track its metadata."""


def create_database_engine(database_url: str, database_path: Path | None = None) -> Engine:
    """Create a SQLite engine, making the parent directory first when a file path is given."""
    if database_path is not None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("creating database engine for %s", database_url)
    return create_engine(database_url, connect_args={"check_same_thread": False})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ping_database(session: Session, database_url: str) -> None:
    """Run a trivial query to prove the database answers; raise a TokenlyError if it does not."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.error("database ping failed for %s: %s", database_url, error)
        raise DatabaseUnavailableError(database_url, error) from error
