"""Learning tests for the overlap findings Phase 4 depends on.

`normalization.categories` asserts that on OpenCode, reasoning and cache tokens are
*additive* to input and output rather than subsets of them. If that ever stops being
true, the whole double-counting design is wrong, so these tests check it against the
developer's real database and fail loudly rather than letting totals drift.

They skip when no OpenCode database is present.
"""

import pytest

from collectors.opencode import OpenCodeCollector
from normalization.categories import OPENCODE_RELATIONSHIPS
from schemas.usage import UsageRecord

UsageRecords = list[UsageRecord]

pytestmark = pytest.mark.usefixtures("real_opencode_records")


@pytest.fixture(scope="module")
def real_opencode_records() -> UsageRecords:
    """Every record from the developer's real OpenCode database, or skip."""
    collector = OpenCodeCollector()
    if not collector.discover().available:
        pytest.skip("no OpenCode database on this machine")
    records = collector.collect_history()
    if not records:
        pytest.skip("OpenCode database holds no completed assistant messages")
    return records


def records_with_reported_total(records: UsageRecords) -> UsageRecords:
    """Records whose source payload carried its own total, for cross-checking."""
    return [r for r in records if (r.raw_usage.get("tokens") or {}).get("total")]


def test_the_reported_total_equals_input_plus_output_plus_reasoning_plus_cache(
    real_opencode_records: UsageRecords,
) -> None:
    """The identity behind the additive claim. Skipped when no record carries a total."""
    with_total = records_with_reported_total(real_opencode_records)
    if not with_total:
        pytest.skip("no record carries a reported total")

    mismatched = [
        r.message_id for r in with_total if r.raw_usage["tokens"]["total"] != r.consumption_tokens
    ]

    assert mismatched == [], "reported total no longer matches the additive sum"


def test_consumption_reproduces_opencode_own_total_on_every_record(
    real_opencode_records: UsageRecords,
) -> None:
    with_total = records_with_reported_total(real_opencode_records)
    if not with_total:
        pytest.skip("no record carries a reported total")

    assert all(r.consumption_tokens == r.raw_usage["tokens"]["total"] for r in with_total)


def test_the_per_call_total_is_never_inflated_by_cache(real_opencode_records: UsageRecords) -> None:
    """Cache reads are large; if they leaked into total_tokens every total would be wrong."""
    for record in real_opencode_records:
        if record.total_tokens is None:
            continue
        assert record.input_tokens is not None
        assert record.output_tokens is not None
        assert record.total_tokens == record.input_tokens + record.output_tokens


def test_cache_reads_exceed_input_on_real_data(real_opencode_records: UsageRecords) -> None:
    """Proof they are not a subset of input: often larger than input itself."""
    pairs = [
        (r.cache_read_tokens, r.input_tokens)
        for r in real_opencode_records
        if r.cache_read_tokens is not None and r.input_tokens is not None
    ]
    if not pairs:
        pytest.skip("no record reports cache reads")

    exceeding = [pair for pair in pairs if pair[0] > pair[1]]

    assert exceeding, "cache reads never exceed input, so the additive claim is untested"


def test_consumption_is_never_less_than_the_per_call_total(
    real_opencode_records: UsageRecords,
) -> None:
    for record in real_opencode_records:
        if record.total_tokens is None or record.consumption_tokens is None:
            continue
        assert record.consumption_tokens >= record.total_tokens


def test_every_record_carries_the_additive_relationship(
    real_opencode_records: UsageRecords,
) -> None:
    for record in real_opencode_records:
        assert record.cache_overlap == OPENCODE_RELATIONSHIPS.cache_overlap
        assert record.reasoning_overlap == OPENCODE_RELATIONSHIPS.reasoning_overlap


def test_no_record_double_counts_input_or_output(real_opencode_records: UsageRecords) -> None:
    """Input and output appear once in consumption, never twice."""
    for record in real_opencode_records:
        if record.consumption_tokens is None:
            continue
        expected = (
            (record.input_tokens or 0)
            + (record.output_tokens or 0)
            + (record.reasoning_tokens or 0)
            + (record.cache_read_tokens or 0)
            + (record.cache_write_tokens or 0)
        )
        assert record.consumption_tokens == expected


def test_all_timestamps_are_timezone_aware_on_real_data(
    real_opencode_records: UsageRecords,
) -> None:
    assert all(record.timestamp.tzinfo is not None for record in real_opencode_records)


def test_unknown_usage_is_null_rather_than_zero_on_real_data(
    real_opencode_records: UsageRecords,
) -> None:
    for record in real_opencode_records:
        if record.usage_status == "unavailable":
            assert record.input_tokens is None
            assert record.total_tokens is None
            assert record.consumption_tokens is None


def test_zero_token_records_keep_a_zero_total(real_opencode_records: UsageRecords) -> None:
    """Aborted calls really did consume nothing; zero must not become null."""
    zero_records = [
        r for r in real_opencode_records if r.input_tokens == 0 and r.output_tokens == 0
    ]
    if not zero_records:
        pytest.skip("no zero-token records present right now")

    assert all(r.total_tokens == 0 for r in zero_records)
