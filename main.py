"""Tokenly backend entry point: wires settings, logging, database, and routes together.

This module is the composition root: every dependency is constructed here and handed to
the code that uses it, so routes stay free of construction logic and tests can build an
app against a temporary database without patching module globals.

The server binds to loopback by default and only allows the configured local frontend
origins, because the data is the user's own usage history and this process is not
meant to be reachable from the network.
"""

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collectors.registry import build_collectors
from config.settings import Settings, get_settings
from database.connection import create_database_engine, create_session_factory
from errors.handlers import register_error_handlers
from logging_setup.configure import configure_logging
from routes.collector import router as collector_router
from routes.health import router as health_router
from routes.usage import router as usage_router

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
    app.state.collectors = build_collectors(resolved_settings)

    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allow_origins,
        allow_methods=resolved_settings.cors_allow_methods,
        allow_headers=resolved_settings.cors_allow_headers,
    )
    app.include_router(health_router)
    app.include_router(usage_router)
    app.include_router(collector_router)

    logger.info(
        "application ready; database at %s, cors origins %s",
        resolved_settings.database_url,
        resolved_settings.cors_allow_origins,
    )
    return app


def run() -> None:
    """Start the API server on the configured host and port."""
    settings = get_settings()
    uvicorn.run(create_app(), host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
