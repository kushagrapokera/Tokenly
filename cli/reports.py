"""Pure, testable data layer for the CLI: a session plus a choice becomes rows.

Nothing here reads input or prints — that is `myusage`'s job. Keeping the queries
pure means every report can be unit-tested against a seeded temporary database
without touching a terminal (Clean Code ch09).
"""

from sqlalchemy.orm import Session

from aggregation.breakdown import ModelUsage, breakdown_by_model
from aggregation.filters import UsageFilter
from aggregation.ranges import resolve_range
from aggregation.summary import UsageSummary, summarize_range

# The windows every report shows, as (range name, human label). Both month
# variants are included so "last month" is never ambiguous.
WINDOWS: tuple[tuple[str, str], ...] = (
    ("all_time", "All time"),
    ("today", "Today"),
    ("last_7_days", "Last 7 days"),
    ("current_month", "This month"),
    ("previous_month", "Last month"),
)


def model_report(
    session: Session, model_id: str, timezone_name: str = "UTC"
) -> list[tuple[str, UsageSummary]]:
    """Return one summary per window for a single model."""
    results: list[tuple[str, UsageSummary]] = []
    for range_name, label in WINDOWS:
        window = resolve_range(range_name, timezone_name)
        summary = summarize_range(session, window, UsageFilter(model_id=model_id))
        results.append((label, summary))
    return results


def provider_report(
    session: Session, provider_id: str, timezone_name: str = "UTC"
) -> list[tuple[str, list[ModelUsage]]]:
    """Return the per-model split for one provider, one entry per window."""
    results: list[tuple[str, list[ModelUsage]]] = []
    for range_name, label in WINDOWS:
        window = resolve_range(range_name, timezone_name)
        rows = breakdown_by_model(session, window, UsageFilter(provider_id=provider_id))
        results.append((label, rows))
    return results


def available_models(session: Session) -> list[tuple[str, int]]:
    """Return (model_id, request_count) across all time, most-used first."""
    return _counts(session, "model_id")


def available_providers(session: Session) -> list[tuple[str, int]]:
    """Return (provider_id, request_count) across all time, most-used first."""
    return _counts(session, "provider_id")


def _counts(session: Session, attribute: str) -> list[tuple[str, int]]:
    """Aggregate the all-time breakdown by one attribute, summing request counts."""
    window = resolve_range("all_time", "UTC")
    counts: dict[str, int] = {}
    for row in breakdown_by_model(session, window):
        value = str(getattr(row, attribute))
        counts[value] = counts.get(value, 0) + row.request_count
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
