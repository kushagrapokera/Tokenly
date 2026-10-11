"""Making sure the database has the schema the ORM expects.

Nothing creates tables on its own. `Base.metadata.create_all` is called by tests
and by the application at startup, so a machine that has never run Tokenly
before still has a usable database the moment the API starts, instead of a file
that answers `SELECT 1` and then fails every real query with
`no such table: usage_events`.

`create_all` only ever issues a `CREATE TABLE` for a table that is missing. It
never drops, renames, or rewrites anything, so starting the application against
a populated database leaves every stored usage event exactly where it was. The
one thing it cannot do is add a column to a table that already exists — that is
what `alembic/versions/` is for, and `tests/test_schema_migrations.py` fails if
a migration and the models ever disagree about the shape of a table.
"""

import logging

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from database.connection import Base

logger = logging.getLogger(__name__)


def ensure_schema(engine: Engine) -> None:
    """Create any table the models declare that the database does not have yet.

    A database that cannot be prepared is a runtime condition this application
    already reports as a 503 from `/api/health`, so the failure is logged and the
    server still starts. Refusing to boot here would replace a clear message with
    a stack trace before the API is even reachable.
    """
    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError as error:
        logger.error("could not prepare the database schema: %s", error)
        return
    logger.info("database schema is ready")