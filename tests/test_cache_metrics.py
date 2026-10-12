"""Cache effectiveness: hit rates, the overlap-aware denominator, and endpoint agreement.

The bug these guard against is a plausible-looking percentage above 100%. Cache reads
are counted against different denominators depending on the provider — already inside
`input_tokens` for Codex, added on top of it for OpenCode, Cline, and Claude Code — so a
single shared denominator reports 3353% for OpenCode on the live store. Each test below
pins one side of that rule.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aggregation import all_time_window, custom_window
from aggregation.breakdown import breakdown_by_model
from aggregation.cache import CacheMetrics, cache_prompt_tokens
from aggregation.summary import summarize_range
from aggregation.timeline import bucket_timeline
from database.connection import Base
from database.repository import upsert_usage_records
from schemas.usage import UsageRecord

UTC = timezone.utc
OCTOBER = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    """A session against a fresh SQLite database with the schema created."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as open_session:
        yield open_session
    engine.dispose()


def cached_record(
    event_id: str,
    *,
    input_tokens: int = 1000,
    cache_read: int = 0,
    cache_write: int = 0,
    cache_overlap: str = "additive",
    provider_id: str = "opencode",
    model_id: str = "example-model",
    minutes: int = 0,
) -> UsageRecord:
    """One record whose cache behaviour is fully specified by the arguments.

    `cache_overlap` is set explicitly rather than inferred, because the whole point is to
    compare what each relationship reports for identical token counts.
    """
    return UsageRecord(
        platform="opencode",
        provider_id=provider_id,
        model_id=model_id,
        session_id="ses_1",
        message_id=event_id,
        source_event_id=event_id,
        timestamp=OCTOBER + timedelta(minutes=minutes),
        input_tokens=input_tokens,
        output_tokens=100,
        total_tokens=input_tokens + 100,
        reasoning_tokens=0,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        consumption_tokens=input_tokens + 100 + cache_read + cache_write,
        cache_overlap=cache_overlap,
        raw_usage={},
    )


def test_request_hit_rate_counts_requests_that_read_cache(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            cached_record("hit_1", cache_read=400),
            cached_record("hit_2", cache_read=400, minutes=1),
            cached_record("miss_1", cache_read=0, minutes=2),
            cached_record("miss_2", cache_read=0, minutes=3),
        ],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert cache.request_count == 4
    assert cache.cache_hit_requests == 2
    assert cache.request_hit_rate == 0.5


def test_additive_providers_count_cache_reads_outside_the_denominator(session: Session) -> None:
    upsert_usage_records(
        session,
        [cached_record("additive_1", input_tokens=1000, cache_read=1000)],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert cache.cache_prompt_tokens == 2000
    assert cache.token_hit_rate == 0.5


def test_subset_providers_keep_the_denominator_equal_to_input(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            cached_record(
                "subset_1",
                input_tokens=1000,
                cache_read=1000,
                cache_overlap="subset_of_input",
            )
        ],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert cache.cache_prompt_tokens == 1000
    assert cache.token_hit_rate == 1.0


def test_a_mixed_group_uses_each_rows_own_relationship(session: Session) -> None:
    """Identical token counts reported under different relationships stay correct.

    Both rows land in one (platform, provider, model) group, so the aggregate has to
    branch per row rather than pick one relationship for the group. Dividing the
    combined 1800 reads by 2000 inputs would report a nonsensical 90%.
    """
    upsert_usage_records(
        session,
        [
            cached_record("as_additive", input_tokens=1000, cache_read=900),
            cached_record(
                "as_subset",
                input_tokens=1000,
                cache_read=900,
                cache_overlap="subset_of_input",
                minutes=1,
            ),
        ],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert cache.cache_read_tokens == 1800
    assert cache.cache_prompt_tokens == 1000 + 1900
    assert cache.token_hit_rate == 1800 / 2900
    assert cache.token_hit_rate <= 1.0


def test_prompt_denominator_branches_on_each_rows_own_relationship() -> None:
    assert cache_prompt_tokens(1000, 400, "subset_of_input") == 1000
    assert cache_prompt_tokens(1000, 400, "additive") == 1400


def test_rates_are_absent_rather_than_zero_when_there_is_no_data() -> None:
    empty = CacheMetrics()

    assert empty.request_hit_rate is None
    assert empty.token_hit_rate is None


def test_cache_write_tokens_are_reported_separately_from_reads(session: Session) -> None:
    upsert_usage_records(
        session,
        [cached_record("write_1", input_tokens=1000, cache_read=400, cache_write=250)],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert cache.cache_read_tokens == 400
    assert cache.cache_write_tokens == 250


def test_summary_and_timeline_agree_on_cache_figures(session: Session) -> None:
    """The SQL aggregate and the in-memory bucket path must report the same numbers.

    Timeline buckets rows in Python while summary groups in SQL. Both apply the
    overlap rule separately, so a change to one and not the other would show the same
    window reporting different cache rates depending on the endpoint asked for.
    """
    upsert_usage_records(
        session,
        [
            cached_record("a_1", input_tokens=1000, cache_read=400),
            cached_record("a_2", input_tokens=1000, cache_read=0, minutes=1),
            cached_record(
                "s_1",
                input_tokens=2000,
                cache_read=1500,
                cache_overlap="subset_of_input",
                minutes=2,
            ),
        ],
    )
    window = custom_window(OCTOBER - timedelta(days=1), OCTOBER + timedelta(days=1), "UTC")

    summary = summarize_range(session, window).cache
    buckets = bucket_timeline(session, window, "day")
    totals = CacheMetrics(
        cache_read_tokens=sum(b.cache.cache_read_tokens for b in buckets),
        cache_write_tokens=sum(b.cache.cache_write_tokens for b in buckets),
        cache_hit_requests=sum(b.cache.cache_hit_requests for b in buckets),
        cache_miss_requests=sum(b.cache.cache_miss_requests for b in buckets),
        cache_unknown_requests=sum(b.cache.cache_unknown_requests for b in buckets),
        cache_prompt_tokens=sum(b.cache.cache_prompt_tokens for b in buckets),
        request_count=sum(b.cache.request_count for b in buckets),
    )

    assert totals == summary


def test_breakdown_reports_cache_per_model_and_provider(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            cached_record("p_1", provider_id="anthropic", model_id="sonnet", cache_read=800),
            cached_record("p_2", provider_id="openrouter", model_id="sonnet", cache_read=100),
            cached_record("p_3", provider_id="anthropic", model_id="opus", cache_read=0),
        ],
    )

    rows = {
        (row.provider_id, row.model_id): row
        for row in breakdown_by_model(session, all_time_window())
    }

    assert rows[("anthropic", "sonnet")].cache.cache_read_tokens == 800
    assert rows[("openrouter", "sonnet")].cache.cache_read_tokens == 100
    assert rows[("anthropic", "opus")].cache.request_hit_rate == 0.0


def test_breakdown_cache_sums_to_the_summary(session: Session) -> None:
    upsert_usage_records(
        session,
        [
            cached_record("s_1", provider_id="anthropic", cache_read=800),
            cached_record("s_2", provider_id="openrouter", cache_read=200),
            cached_record("s_3", provider_id="openrouter", cache_read=0, minutes=1),
        ],
    )
    window = all_time_window()

    summary = summarize_range(session, window).cache
    rows = breakdown_by_model(session, window)

    assert sum(row.cache.cache_read_tokens for row in rows) == summary.cache_read_tokens
    assert sum(row.cache.cache_hit_requests for row in rows) == summary.cache_hit_requests
    assert sum(row.cache.cache_prompt_tokens for row in rows) == summary.cache_prompt_tokens


def test_missing_cache_data_never_inflates_the_hit_rate(session: Session) -> None:
    """A row whose cache data was never reported is unknown, not a miss.

    Folding unknowns into the misses would report 1/2 = 50% hits when the source only ever
    spoke about one request, and that one did hit. It would also make a provider that
    stopped reporting cache data look like one whose cache stopped working.
    """
    upsert_usage_records(
        session,
        [
            cached_record("known", cache_read=500),
            UsageRecord(
                platform="opencode",
                provider_id="opencode",
                model_id="example-model",
                session_id="ses_1",
                message_id="unknown",
                source_event_id="unknown",
                timestamp=OCTOBER + timedelta(minutes=1),
                input_tokens=200,
                output_tokens=50,
                total_tokens=250,
                cache_read_tokens=None,
                cache_write_tokens=None,
                usage_status="unavailable",
            ),
        ],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert cache.request_count == 2
    assert cache.cache_hit_requests == 1
    assert cache.cache_miss_requests == 0
    assert cache.cache_unknown_requests == 1
    assert cache.cache_known_requests == 1
    assert cache.request_hit_rate == 1.0


def test_every_request_lands_in_exactly_one_cache_outcome(session: Session) -> None:
    """Hits, misses, and unknowns must account for every request, with none doubled."""
    upsert_usage_records(
        session,
        [
            cached_record("hit", cache_read=500),
            cached_record("miss", cache_read=0, minutes=1),
            UsageRecord(
                platform="opencode",
                provider_id="opencode",
                model_id="example-model",
                session_id="ses_1",
                message_id="unknown",
                source_event_id="unknown",
                timestamp=OCTOBER + timedelta(minutes=2),
                input_tokens=200,
                output_tokens=50,
                total_tokens=250,
                cache_read_tokens=None,
                usage_status="unavailable",
            ),
        ],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert (
        cache.cache_hit_requests + cache.cache_miss_requests + cache.cache_unknown_requests
        == cache.request_count
    )
    assert cache.request_hit_rate == 1 / 2


def test_unknown_cache_data_leaves_the_token_rate_unchanged(session: Session) -> None:
    """A row with no cache data contributes no prompt denominator.

    Adding its input to the denominator would silently drag the token hit rate down for
    data that says nothing about whether the cache was used.
    """
    upsert_usage_records(
        session,
        [
            cached_record("known", input_tokens=1000, cache_read=500),
            UsageRecord(
                platform="opencode",
                provider_id="opencode",
                model_id="example-model",
                session_id="ses_1",
                message_id="unknown",
                source_event_id="unknown",
                timestamp=OCTOBER + timedelta(minutes=1),
                input_tokens=9999,
                output_tokens=50,
                total_tokens=10049,
                cache_read_tokens=None,
                usage_status="unavailable",
            ),
        ],
    )

    cache = summarize_range(session, all_time_window()).cache

    assert cache.cache_prompt_tokens == 1500
    assert cache.token_hit_rate == 1 / 3