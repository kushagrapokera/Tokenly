"""Tokenly backend entry point: wires settings, logging, database, and routes together.

This module is the composition root: every dependency is constructed here and handed to
the code that uses it, so routes stay free of construction logic and tests can build an
app against a temporary database without patching module globals.

The server binds to loopback by default and only allows the configured local frontend
origins, because the data is the user's own usage history and this process is not
meant to be reachable from the network.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collectors.registry import build_collectors
from config.settings import Settings, get_settings
from database.connection import create_database_engine, create_session_factory
from database.schema import ensure_schema
from errors.handlers import register_error_handlers
from logging_setup.configure import configure_logging
from routes.collector import router as collector_router
from routes.health import router as health_router
from routes.usage import router as usage_router
from sync.coordinator import build_sync_coordinator
from sync.scheduler import SyncScheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run collection in the background for as long as the server is up.

    The first pass is not awaited: a cold history can take seconds to import, and
    blocking startup on it would leave the dashboard unreachable for exactly as
    long as the user is waiting. The collector status endpoint reports `scanning`
    while it works. Shutdown sets the stop event and waits for the pass to
    finish, so no scan is abandoned halfway through.
    """
    if not app.state.settings.sync_enabled:
        logger.info("automatic collection is disabled; use the rescan endpoint instead")
        yield
        return

    scheduler = SyncScheduler(
        build_sync_coordinator(app.state.collectors, app.state.settings),
        app.state.session_factory,
        app.state.settings.sync_interval_seconds,
    )
    app.state.sync_scheduler = scheduler
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler.run_periodically(stop))
    logger.info(
        "collection started for %s every %.0f seconds",
        scheduler.platforms,
        scheduler.interval_seconds,
    )
    try:
        yield
    finally:
        stop.set()
        await task
        logger.info("collection stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. All construction happens here; routes only use what they are given."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    logger.info("assembling %s %s", resolved_settings.app_name, resolved_settings.app_version)

    engine = create_database_engine(
        resolved_settings.database_url,
        database_path=resolved_settings.database_path,
    )
    ensure_schema(engine)
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
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
