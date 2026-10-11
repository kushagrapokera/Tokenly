"""Response bodies for the usage endpoints.

These models are the API's contract with the dashboard, so they are built from the
aggregation dataclasses in one place (`from_*` constructors) rather than assembled
field by field inside routes. Every response repeats the same envelope — `window`,
`filters`, `generated_at` — so a client can render any chart from any endpoint without
special-casing the response shape.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from aggregation.breakdown import ModelUsage
from aggregation.filters import UsageFilter
from aggregation.ranges import DEFAULT_RANGE
from aggregation.summary import UsageSummary
from aggregation.timeline import TimeBucket
from aggregation.windows import TimeWindow

Granularity = str


def _now() -> datetime:
    """Return the response generation time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


class WindowInfo(BaseModel):
    """The interval a response covers, so a client can label it without guessing."""

    range: str = DEFAULT_RANGE
    label: str
    start: datetime | None = None
    end: datetime | None = None
    timezone: str = "UTC"


class AppliedFilters(BaseModel):
    """The dimensions a response was narrowed by; unset fields mean 'no filter'."""

    platform: str | None = None
    provider_id: str | None = None
    model_id: str | None = None

    @classmethod
    def from_filters(cls, filters: UsageFilter | None) -> AppliedFilters:
        """Describe the filter that was applied to the query."""
        active = filters or UsageFilter()
        return cls(
            platform=active.platform,
            provider_id=active.provider_id,
            model_id=active.model_id,
        )


class CompletenessInfo(BaseModel):
    """How much of the picture is backed by real numbers.

    `unknown_total_events` counts usage rows whose total the source never reported.
    Those rows contribute zero to `total_tokens`, so a client that shows only totals
    must also show this, or it will present partial data as complete.
    """

    request_count: int
    known_total_events: int
    unknown_total_events: int
    is_complete: bool


class UsageTotals(BaseModel):
    """Token totals for one interval."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    consumption_tokens: int


class SummaryResponse(BaseModel):
    """Totals for one named range, as shown on the dashboard's headline cards."""

    window: WindowInfo
    filters: AppliedFilters
    totals: UsageTotals
    completeness: CompletenessInfo
    generated_at: datetime = Field(default_factory=_now)

    @classmethod
    def from_summary(
        cls,
        summary: UsageSummary,
        window: TimeWindow,
        range_name: str,
        filters: UsageFilter | None = None,
    ) -> SummaryResponse:
        """Wrap one aggregation summary in the standard response envelope."""
        return cls(
            window=_window_info(window, range_name),
            filters=AppliedFilters.from_filters(filters),
            totals=UsageTotals(
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                total_tokens=summary.total_tokens,
                consumption_tokens=summary.consumption_tokens,
            ),
            completeness=CompletenessInfo(
                request_count=summary.request_count,
                known_total_events=summary.known_total_events,
                unknown_total_events=summary.unknown_total_events,
                is_complete=summary.unknown_total_events == 0,
            ),
        )


class ModelUsageResponse(BaseModel):
    """One (provider, model) pair's totals.

    Provider and model are reported separately because two providers can serve the
    same model name, and attributing one's usage to the other would be wrong.
    """

    provider_id: str
    model_id: str
    request_count: int
    totals: UsageTotals
    unknown_total_events: int


class ModelBreakdownResponse(BaseModel):
    """Model-wise usage for a range, ordered by total tokens descending."""

    window: WindowInfo
    filters: AppliedFilters
    models: list[ModelUsageResponse]
    generated_at: datetime = Field(default_factory=_now)

    @classmethod
    def from_models(
        cls,
        models: list[ModelUsage],
        window: TimeWindow,
        range_name: str,
        filters: UsageFilter | None = None,
    ) -> ModelBreakdownResponse:
        """Wrap a model breakdown in the standard response envelope."""
        return cls(
            window=_window_info(window, range_name),
            filters=AppliedFilters.from_filters(filters),
            models=[_model_usage(model) for model in models],
        )


class TimelineBucketResponse(BaseModel):
    """Totals for one calendar bucket; empty buckets are included as zeroes."""

    start: datetime
    label: str
    request_count: int
    totals: UsageTotals


class TimelineResponse(BaseModel):
    """Bucketed totals for a range, ready to plot without further processing."""

    window: WindowInfo
    filters: AppliedFilters
    granularity: Granularity
    buckets: list[TimelineBucketResponse]
    generated_at: datetime = Field(default_factory=_now)

    @classmethod
    def from_buckets(
        cls,
        buckets: list[TimeBucket],
        window: TimeWindow,
        range_name: str,
        granularity: Granularity,
        filters: UsageFilter | None = None,
    ) -> TimelineResponse:
        """Wrap timeline buckets in the standard response envelope."""
        return cls(
            window=_window_info(window, range_name),
            filters=AppliedFilters.from_filters(filters),
            granularity=granularity,
            buckets=[
                TimelineBucketResponse(
                    start=bucket.bucket_start,
                    label=bucket.bucket_label,
                    request_count=bucket.request_count,
                    totals=UsageTotals(
                        input_tokens=bucket.input_tokens,
                        output_tokens=bucket.output_tokens,
                        total_tokens=bucket.total_tokens,
                        consumption_tokens=bucket.consumption_tokens,
                    ),
                )
                for bucket in buckets
            ],
        )


def _window_info(window: TimeWindow, range_name: str) -> WindowInfo:
    """Describe a window for the client, keeping the requested range name."""
    return WindowInfo(
        range=range_name,
        label=window.label,
        start=window.start,
        end=window.end,
        timezone=window.timezone_name,
    )


def _model_usage(model: ModelUsage) -> ModelUsageResponse:
    """Convert one breakdown row into its response shape."""
    return ModelUsageResponse(
        provider_id=model.provider_id,
        model_id=model.model_id,
        request_count=model.request_count,
        totals=UsageTotals(
            input_tokens=model.input_tokens,
            output_tokens=model.output_tokens,
            total_tokens=model.total_tokens,
            consumption_tokens=model.consumption_tokens,
        ),
        unknown_total_events=model.unknown_total_events,
    )


__all__ = [
    "AppliedFilters",
    "CompletenessInfo",
    "Granularity",
    "ModelBreakdownResponse",
    "ModelUsageResponse",
    "SummaryResponse",
    "TimelineBucketResponse",
    "TimelineResponse",
    "UsageTotals",
    "WindowInfo",
]
