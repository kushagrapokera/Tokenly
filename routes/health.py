"""Health check endpoint."""

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database.connection import ping_database
from errors.exceptions import DatabaseUnavailableError
from schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def get_session(request: Request) -> Iterator[Session]:
    """Hand the route one database session per request, always closed afterwards."""
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/api/health", response_model=HealthResponse)
def read_health(
    request: Request,
    session: SessionDependency,
) -> HealthResponse:
    """Report application health, including whether the database answers queries."""
    settings = request.app.state.settings
    try:
        ping_database(session, settings.database_url)
    except DatabaseUnavailableError:
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        database_connected=True,
    )
