"""Turning domain errors into HTTP responses.

Each error Tokenly raises already knows what it means; this module is the single place
that decides which status code the client sees. Without it, a bad timezone would come
back as an opaque 500 and the dashboard could not tell a mistake in the request from a
failure on this machine.
"""

import logging
from collections.abc import Callable
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler

from collectors.checkpoint import InvalidCheckpointError
from errors.exceptions import (
    AggregationError,
    ApiError,
    CollectorError,
    DatabaseUnavailableError,
    TokenlyError,
)

logger = logging.getLogger(__name__)

UNKNOWN_ERROR_STATUS = status.HTTP_500_INTERNAL_SERVER_ERROR


def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    """Return the status the error itself asks for, with its message as the detail."""
    log = logger.warning if error.status_code < 500 else logger.error
    log("%s %s failed: %s", request.method, request.url.path, error.detail)
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail, "error": type(error).__name__},
    )


def aggregation_error_handler(request: Request, error: AggregationError) -> JSONResponse:
    """Report a bad aggregation request as a client mistake, not a server fault.

    Unknown timezones, inverted ranges, and unsupported granularities are all things the
    caller can correct, so they become 400s with the reason attached.
    """
    logger.warning(
        "%s %s has an invalid aggregation request: %s", request.method, request.url.path, error
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(error), "error": type(error).__name__},
    )


def collector_error_handler(request: Request, error: CollectorError) -> JSONResponse:
    """Report a collector failure as a bad gateway.

    The collector is a dependency outside this service, so failing to read it is not
    the client's fault and is not a fault in the API either. `InvalidCheckpointError`
    means stored state is unreadable, which is a fault on this side, so it is logged at
    error level and returned as a 500 through the generic handler.
    """
    if isinstance(error, InvalidCheckpointError):
        return tokenly_error_handler(request, error)
    logger.warning("collector failed for %s %s: %s", request.method, request.url.path, error)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(error), "error": type(error).__name__},
    )


def database_error_handler(request: Request, error: DatabaseUnavailableError) -> JSONResponse:
    """Report an unreachable database as temporarily unavailable, so clients retry."""
    logger.error("database unavailable for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "database unavailable", "error": type(error).__name__},
    )


def tokenly_error_handler(request: Request, error: TokenlyError) -> JSONResponse:
    """Return a last-resort body for any Tokenly error with no handler of its own.

    The message is included because these errors are written to be read by a developer
    debugging a local install; anything not raised deliberately is left to Starlette.
    """
    logger.exception("unhandled Tokenly error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=UNKNOWN_ERROR_STATUS,
        content={"detail": str(error), "error": type(error).__name__},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach every handler so routes can raise domain errors without catching them.

    FastAPI picks the most specific registered class when an error is raised, so a
    `CollectorError` subclass with a handler of its own still wins over the base entry.

    The handlers are declared as taking `Exception` because that is the signature
    Starlette calls them with; each one narrows to its own error type and the
    registration below guarantees it only ever receives that type.
    """
    _register(app, ApiError, api_error_handler)
    _register(app, AggregationError, aggregation_error_handler)
    _register(app, CollectorError, collector_error_handler)
    _register(app, DatabaseUnavailableError, database_error_handler)
    _register(app, TokenlyError, tokenly_error_handler)


def _register(
    app: FastAPI,
    error_type: type[TokenlyError],
    handler: Callable[[Request, Any], JSONResponse],
) -> None:
    """Register one handler, widening its signature to what Starlette expects."""
    app.add_exception_handler(error_type, cast(ExceptionHandler, handler))


__all__ = ["register_error_handlers"]
