"""Health check endpoint."""

import logging

from fastapi import APIRouter, Request

from database.connection import ping_database
from errors.exceptions import DatabaseUnavailableError, ServiceUnavailableError
from routes.dependencies import SessionDependency
from schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


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
        raise ServiceUnavailableError("database unavailable") from None
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        database_connected=True,
    )
