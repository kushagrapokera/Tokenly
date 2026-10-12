"""Cache effectiveness: how often the prompt cache fired, and how much it saved.

Two rates, because they answer different questions and they are not the same number:

* **Request hit rate** — `cache_hit_requests / cache_known_requests`. How often a request
  found a usable cache. Overlap-agnostic: a request either read cached tokens or it did
  not, whatever those tokens are counted against.
* **Token hit rate** — `cache_read_tokens / cache_prompt_tokens`. How much of the prompt
  actually came from cache instead of being sent fresh.

The token rate needs the denominator to be overlap-aware, which is the whole subtlety.
`cache_overlap` records whether a row's cached tokens are already inside `input_tokens`
(`subset_of_input`, Codex) or sit on top of it (`additive`, OpenCode/Cline/Claude Code).
Dividing by one fixed denominator gets one platform right and the others badly wrong:
across the live store, `cache_read / input` reports 3353% for OpenCode and 1659% for
Claude Code, because their `input_tokens` excludes the very tokens being measured. So the
denominator is computed per row from that row's own `cache_overlap`, which also keeps a
group correct even if it mixes both relationships.

**Unknown is not a miss.** A row whose source never reported `cache_read_tokens` is
counted in `cache_unknown_requests`, not in `cache_miss_requests`, and every rate divides
by the requests the source actually spoke about. Folding unknowns into the misses would
report Cline at 90.9% hits instead of its true 91.5%, and would make a provider that
stopped reporting cache data look like one whose cache stopped working — the opposite of
what happened. This follows the project rule that incomplete coverage is reported
alongside the totals, never silently absorbed into them.

This module is the only place that arithmetic lives. `summary`, `breakdown`, and
`timeline` all pull their columns from here, so the three endpoints cannot drift apart.
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Integer, case, func

from database.models import UsageEvent
from normalization.categories import ADDITIVE_CACHE, SUBSET_OF_INPUT, CacheOverlap

logger = logging.getLogger(__name__)

CACHE_ROW_COLUMNS: tuple[Any, ...] = (
    UsageEvent.cache_read_tokens,
    UsageEvent.cache_write_tokens,
    UsageEvent.cache_overlap,
)


@dataclass(frozen=True)
class CacheMetrics:
    """Cache totals for a group of usage events, plus both effectiveness rates.

    Every request lands in exactly one of `cache_hit_requests` (read from cache),
    `cache_miss_requests` (reported zero), or `cache_unknown_requests` (the source never
    said). Keeping the third bucket separate is what lets the rates measure the cache
    rather than the reporting gaps.

    `cache_prompt_tokens` is the overlap-aware denominator: for additive providers it is
    `input + cache_read`, because both reached the model; for `subset_of_input` providers
    the cached portion is already inside `input`, so adding it again would double-count.
    It is stored rather than recomputed so callers cannot divide by the wrong column.
    """

    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_hit_requests: int = 0
    cache_miss_requests: int = 0
    cache_unknown_requests: int = 0
    cache_prompt_tokens: int = 0
    request_count: int = 0

    @property
    def cache_known_requests(self) -> int:
        """Requests the source actually reported cache data for."""
        return self.cache_hit_requests + self.cache_miss_requests

    @property
    def request_hit_rate(self) -> float | None:
        """Fraction of known requests that read from cache, None when there were none.

        Divides by the known requests, not the total, so rows whose cache data was never
        reported lower neither the numerator nor the denominator.
        """
        return _rate(self.cache_hit_requests, self.cache_known_requests)

    @property
    def token_hit_rate(self) -> float | None:
        """Fraction of prompt tokens served from cache, None when none were eligible."""
        return _rate(self.cache_read_tokens, self.cache_prompt_tokens)


def cache_group_columns() -> tuple[Any, ...]:
    """Labeled SQL aggregates for the cache columns, for use in a GROUP BY query."""
    return (
        func.coalesce(func.sum(UsageEvent.cache_read_tokens), 0).label("cache_read_tokens"),
        func.coalesce(func.sum(UsageEvent.cache_write_tokens), 0).label("cache_write_tokens"),
        _cache_hit_count_expression().label("cache_hit_requests"),
        _cache_miss_count_expression().label("cache_miss_requests"),
        _cache_unknown_count_expression().label("cache_unknown_requests"),
        _cache_prompt_tokens_expression().label("cache_prompt_tokens"),
    )


def metrics_from_grouped_row(row: Any, request_count: int) -> CacheMetrics:
    """Build `CacheMetrics` from a row returned by `cache_group_columns`."""
    return CacheMetrics(
        cache_read_tokens=int(row.cache_read_tokens),
        cache_write_tokens=int(row.cache_write_tokens),
        cache_hit_requests=int(row.cache_hit_requests),
        cache_miss_requests=int(row.cache_miss_requests),
        cache_unknown_requests=int(row.cache_unknown_requests),
        cache_prompt_tokens=int(row.cache_prompt_tokens),
        request_count=request_count,
    )


def metrics_from_usage_row(row: Any) -> CacheMetrics:
    """Build `CacheMetrics` for a single raw usage event, timeline-style.

    The timeline reads rows and buckets them in memory rather than grouping in SQL, so it
    applies the same per-row overlap rule the SQL aggregate uses. Both paths must agree,
    or the same window would report different cache rates depending on the endpoint.
    """
    cache_read = row.cache_read_tokens
    input_tokens = int(row.input_tokens or 0)
    overlap: CacheOverlap = row.cache_overlap or ADDITIVE_CACHE
    if cache_read is None:
        return CacheMetrics(request_count=1, cache_unknown_requests=1)
    read_tokens = int(cache_read)
    return CacheMetrics(
        cache_read_tokens=read_tokens,
        cache_write_tokens=int(row.cache_write_tokens or 0),
        cache_hit_requests=1 if read_tokens > 0 else 0,
        cache_miss_requests=0 if read_tokens > 0 else 1,
        cache_prompt_tokens=cache_prompt_tokens(input_tokens, read_tokens, overlap),
        request_count=1,
    )


def cache_prompt_tokens(input_tokens: int, cache_read: int, overlap: CacheOverlap) -> int:
    """Overlap-aware prompt denominator for one row of tokens."""
    if overlap == SUBSET_OF_INPUT:
        return input_tokens
    return input_tokens + cache_read


def _cache_hit_count_expression() -> Any:
    """Count rows that actually read cached tokens."""
    return func.coalesce(
        func.sum(case((UsageEvent.cache_read_tokens > 0, 1), else_=0)), 0
    ).cast(Integer)


def _cache_miss_count_expression() -> Any:
    """Count rows that reported zero cached tokens — a genuine cache miss."""
    return func.coalesce(
        func.sum(case((UsageEvent.cache_read_tokens == 0, 1), else_=0)), 0
    ).cast(Integer)


def _cache_unknown_count_expression() -> Any:
    """Count rows whose source never reported cache data, kept out of both of the above."""
    return func.coalesce(
        func.sum(case((UsageEvent.cache_read_tokens.is_(None), 1), else_=0)), 0
    ).cast(Integer)


def _cache_prompt_tokens_expression() -> Any:
    """Sum the overlap-aware prompt denominator, branching on each row's relationship.

    Rows whose cache data was never reported contribute nothing. Their input tokens are
    known but their cache reads are not, so including them would drag the token hit rate
    down on the strength of data that says nothing about whether the cache was used.
    """
    fresh_input = func.coalesce(UsageEvent.input_tokens, 0)
    cache_read = func.coalesce(UsageEvent.cache_read_tokens, 0)
    reported = UsageEvent.cache_read_tokens.is_not(None)
    return func.coalesce(
        func.sum(
            case(
                (~reported, 0),
                (UsageEvent.cache_overlap == SUBSET_OF_INPUT, fresh_input),
                else_=fresh_input + cache_read,
            )
        ),
        0,
    ).cast(Integer)


def _rate(numerator: int, denominator: int) -> float | None:
    """Divide safely, reporting None rather than a misleading zero when there is no data."""
    if denominator <= 0:
        logger.debug("cache rate undefined: empty denominator (%d/%d)", numerator, denominator)
        return None
    return numerator / denominator