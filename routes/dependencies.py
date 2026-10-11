"""Reusable request dependencies: the database session and shared query parameters.

Every usage endpoint accepts the same range, timezone, and filter parameters, and every
one needs a session. Defining that once keeps the routes to a single statement each and
means the parameter contract is written down in a single place.

Window *validation* stays in `aggregation.ranges` and `aggregation.windows`: a route
resolves a window through those modules and lets the raised domain errors reach the
handlers in `errors.handlers`, so no route repeats the same try/except.
"""

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Path, Query, Request
from sqlalchemy.orm import Session

from aggregation.filters import UsageFilter
from aggregation.ranges import DEFAULT_RANGE, RANGE_NAMES
from config.settings import Settings

logger = logging.getLogger(__name__)


def get_session(request: Request) -> Iterator[Session]:
    """Hand the route one database session per request, always closed afterwards."""
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


def get_settings(request: Request) -> Settings:
    """Expose the process settings to routes that need them."""
    settings: Settings = request.app.state.settings
    return settings


SessionDependency = Annotated[Session, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]

RangeQuery = Annotated[
    str,
    Query(
        alias="range",
        description="Named time range; 'custom' requires both start and end.",
        json_schema_extra={"enum": list(RANGE_NAMES)},
    ),
]

TimezoneQuery = Annotated[
    str | None,
    Query(alias="timezone", description="IANA timezone the calendar boundaries are built in."),
]

StartQuery = Annotated[
    datetime | None,
    Query(description="Inclusive start of a custom range; ignored by named ranges."),
]

EndQuery = Annotated[
    datetime | None,
    Query(description="Exclusive end of a custom range; ignored by named ranges."),
]

PlatformQuery = Annotated[str | None, Query(description="Restrict to one platform.")]

ProviderQuery = Annotated[str | None, Query(description="Restrict to one provider.")]

ModelQuery = Annotated[str | None, Query(description="Restrict to one model.")]

GranularityQuery = Annotated[
    str,
    Query(
        description="Bucket size for a timeline.",
        json_schema_extra={"enum": ["day", "month", "year"]},
    ),
]

PlatformPath = Annotated[str, Path(description="Platform identifier, e.g. 'opencode'.")]


@dataclass(frozen=True)
class UsageRequest:
    """What one request asked for, before a window has been built from it."""

    range_name: str
    timezone_name: str
    filters: UsageFilter
    start: datetime | None = None
    end: datetime | None = None


def usage_request(
    settings: SettingsDependency,
    range_name: RangeQuery = DEFAULT_RANGE,
    timezone_name: TimezoneQuery = None,
    start: StartQuery = None,
    end: EndQuery = None,
    platform: PlatformQuery = None,
    provider_id: ProviderQuery = None,
    model_id: ModelQuery = None,
) -> UsageRequest:
    """Collect the shared usage query parameters into one object.

    An absent timezone falls back to the configured default, so a client that does not
    know the user's location still gets correct calendar boundaries. An absent range
    falls back to `default_range`, which is what lets each endpoint have its own
    sensible default while sharing one parameter contract.
    """
    request = UsageRequest(
        range_name=range_name.strip() or DEFAULT_RANGE,
        timezone_name=(timezone_name or settings.default_timezone).strip(),
        filters=UsageFilter(platform=platform, provider_id=provider_id, model_id=model_id),
        start=start,
        end=end,
    )
    logger.info(
        "usage request: range=%s timezone=%s filters=%s",
        request.range_name,
        request.timezone_name,
        request.filters,
    )
    return request


def usage_request_for(default_range: str) -> Callable[..., UsageRequest]:
    """Build a dependency that resolves usage queries against a specific default range.

    The dashboard's cards and its chart endpoints want different defaults from the same
    parameters, so the default is bound per endpoint instead of duplicated per route.
    """
    logger.debug("binding usage dependency with default range %s", default_range)

    def dependency(
        settings: SettingsDependency,
        range_name: RangeQuery = default_range,
        timezone_name: TimezoneQuery = None,
        start: StartQuery = None,
        end: EndQuery = None,
        platform: PlatformQuery = None,
        provider_id: ProviderQuery = None,
        model_id: ModelQuery = None,
    ) -> UsageRequest:
        """Resolve the shared usage parameters, defaulting the range to this endpoint's."""
        return usage_request(
            settings,
            range_name=range_name or default_range,
            timezone_name=timezone_name,
            start=start,
            end=end,
            platform=platform,
            provider_id=provider_id,
            model_id=model_id,
        )

    return dependency


__all__ = [
    "EndQuery",
    "GranularityQuery",
    "ModelQuery",
    "PlatformPath",
    "PlatformQuery",
    "ProviderQuery",
    "RangeQuery",
    "SessionDependency",
    "SettingsDependency",
    "StartQuery",
    "TimezoneQuery",
    "UsageRequest",
    "get_session",
    "get_settings",
    "usage_request",
    "usage_request_for",
]
