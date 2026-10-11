"""Usage endpoints: summaries, calendar series, model breakdown, and timelines.

Every endpoint resolves its window through `aggregation.ranges`, so the timezone rules
built in Phase 7 hold here without being restated, and every response is built by
`schemas.analytics` so the shape is identical across endpoints.

An empty result is a valid answer, not an error: a range with no usage returns zeroes
and an empty list, with `completeness` making clear whether that means "no usage" or
"usage whose totals the source never reported".
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from aggregation.breakdown import breakdown_by_model
from aggregation.ranges import (
    RANGE_ALL_TIME,
    RANGE_CURRENT_YEAR,
    RANGE_LAST_7_DAYS,
    resolve_range,
    resolve_range_for_timeline,
)
from aggregation.summary import summarize_range
from aggregation.timeline import bucket_timeline
from aggregation.windows import TimeWindow
from routes.dependencies import (
    GranularityQuery,
    SessionDependency,
    UsageRequest,
    usage_request_for,
)
from schemas.analytics import ModelBreakdownResponse, SummaryResponse, TimelineResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/usage", tags=["usage"])

DEFAULT_GRANULARITY = "day"


@router.get("/summary", response_model=SummaryResponse)
def read_summary(
    session: SessionDependency,
    request: Annotated[UsageRequest, Depends(usage_request_for(RANGE_ALL_TIME))],
) -> SummaryResponse:
    """Return total token usage for one range.

    The same endpoint serves every headline card: today, this month, this year, and
    all time differ only in `range`. It defaults to all time because a card showing a
    number with no stated period is most useful as the lifetime total.
    """
    window = _window_for(request)
    summary = summarize_range(session, window, request.filters)
    return SummaryResponse.from_summary(summary, window, request.range_name, request.filters)


@router.get("/daily", response_model=TimelineResponse)
def read_daily(
    session: SessionDependency,
    request: Annotated[UsageRequest, Depends(usage_request_for(RANGE_LAST_7_DAYS))],
) -> TimelineResponse:
    """Return one bucket per calendar day across the requested range."""
    return _timeline(session, request, "day")


@router.get("/monthly", response_model=TimelineResponse)
def read_monthly(
    session: SessionDependency,
    request: Annotated[UsageRequest, Depends(usage_request_for(RANGE_CURRENT_YEAR))],
) -> TimelineResponse:
    """Return one bucket per calendar month across the requested range.

    Defaults to the current year so the bar chart has several months to show rather
    than the single month `current_month` would return.
    """
    return _timeline(session, request, "month")


@router.get("/yearly", response_model=TimelineResponse)
def read_yearly(
    session: SessionDependency,
    request: Annotated[UsageRequest, Depends(usage_request_for(RANGE_ALL_TIME))],
) -> TimelineResponse:
    """Return one bucket per calendar year across the requested range."""
    return _timeline(session, request, "year")


@router.get("/models", response_model=ModelBreakdownResponse)
def read_models(
    session: SessionDependency,
    request: Annotated[UsageRequest, Depends(usage_request_for(RANGE_ALL_TIME))],
) -> ModelBreakdownResponse:
    """Return per-(provider, model) totals, ordered by total tokens descending."""
    window = _window_for(request)
    models = breakdown_by_model(session, window, request.filters)
    return ModelBreakdownResponse.from_models(models, window, request.range_name, request.filters)


@router.get("/timeline", response_model=TimelineResponse)
def read_timeline(
    request: Annotated[UsageRequest, Depends(usage_request_for(RANGE_LAST_7_DAYS))],
    session: SessionDependency,
    granularity: GranularityQuery = DEFAULT_GRANULARITY,
) -> TimelineResponse:
    """Return bucketed totals at a caller-chosen granularity."""
    return _timeline(session, request, granularity)


def _window_for(request: UsageRequest) -> TimeWindow:
    """Build the exact window the request asked for, honouring custom bounds."""
    return resolve_range(
        request.range_name,
        request.timezone_name,
        start=request.start,
        end=request.end,
    )


def _timeline(
    session: SessionDependency,
    request: UsageRequest,
    granularity: str,
) -> TimelineResponse:
    """Bucket the requested window and wrap the result in the shared envelope."""
    window = resolve_range_for_timeline(
        request.range_name,
        request.timezone_name,
        start=request.start,
        end=request.end,
    )
    buckets = bucket_timeline(session, window, granularity, request.filters)
    logger.debug(
        "timeline for %s produced %d %s buckets", request.range_name, len(buckets), granularity
    )
    return TimelineResponse.from_buckets(
        buckets,
        window,
        request.range_name,
        granularity,
        request.filters,
    )


__all__ = ["router"]
