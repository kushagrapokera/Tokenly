"""Tokenly backend entry point: wires settings, logging, database, and routes together."""

import logging

import uvicorn
from fastapi import FastAPI

from config.settings import Settings, get_settings
from database.connection import create_database_engine, create_session_factory
from logging_setup.configure import configure_logging
from routes.health import router as health_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. All construction happens here; routes only use what they are given."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    logger.info("assembling %s %s", resolved_settings.app_name, resolved_settings.app_version)

    engine = create_database_engine(
        resolved_settings.database_url,
        database_path=resolved_settings.database_path,
    )
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
    )
    app.state.settings = resolved_settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.include_router(health_router)

    logger.info("application ready; database at %s", resolved_settings.database_url)
    return app


def run() -> None:
    """Start the API server on the configured host and port."""
    settings = get_settings()
    uvicorn.run(create_app(), host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
