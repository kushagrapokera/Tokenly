"""Tests for token normalization: one per Phase 4 rule."""

from datetime import datetime, timezone

import pytest

from normalization.categories import CategoryRelationships
from normalization.normalizer import normalize_timestamp, normalize_usage_record
from normalization.status import resolve_usage_status
from normalization.totals import (
    TokenCategories,
    calculate_totals,
    read_count,
    sum_every_category,
    token_categories_from_mapping,
)

ADDITIVE = CategoryRelationships(cache_overlap="additive", reasoning_overlap="additive")
SUBSET = CategoryRelationships(
    cache_overlap="subset_of_input", reasoning_overlap="subset_of_output"
)


def categories(**kwargs: int | None) -> TokenCategories:
    return TokenCategories(**kwargs)


# --- rule 1: provider and model identifiers are preserved unchanged ---


def test_provider_and_model_identifiers_pass_through_untouched() -> None:
    record = normalize_usage_record(
        platform="opencode",
        provider_id="opencode",
        model_id="muse-spark-1.3-contributor-free",
        session_id="ses_1",
        message_id="msg_1",
        source_event_id="msg_1",
        timestamp=datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc),
        raw_tokens={"input": 10, "output": 5},
        relationships=ADDITIVE,
    )

    assert record.provider_id == "opencode"
    assert record.model_id == "muse-spark-1.3-contributor-free"


# --- rule 2: timestamps are normalized to UTC ---


def test_a_naive_timestamp_is_treated_as_utc() -> None:
    assert normalize_timestamp(datetime(2026, 10, 10, 12, 0)) == datetime(
        2026, 10, 10, 12, 0, tzinfo=timezone.utc
    )


def test_an_offset_timestamp_is_converted_to_utc() -> None:
    from datetime import timedelta

    offset = timezone(timedelta(hours=5, minutes=30))
    moment = datetime(2026, 10, 10, 12, 0, tzinfo=offset)

    normalized = normalize_timestamp(moment)

    assert normalized == datetime(2026, 10, 10, 6, 30, tzinfo=timezone.utc)
    assert normalized.utcoffset() == timedelta(0)


# --- rule 3: nonnegative integer token counts ---


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (42, 42), (-1, None), (True, None), ("7", None), (3.5, None), (None, None)],
)
def test_only_nonnegative_integers_are_accepted(value: object, expected: int | None) -> None:
    assert read_count(value) == expected


# --- rule 4: unavailable values are null, never zero ---


def test_missing_input_leaves_the_total_unknown_rather_than_partial() -> None:
    record = normalize_usage_record(
        platform="opencode",
        provider_id="opencode",
        model_id="m",
        session_id="ses_1",
        message_id="msg_1",
        source_event_id="msg_1",
        timestamp=datetime(2026, 10, 10, tzinfo=timezone.utc),
        raw_tokens={"output": 5},
        relationships=ADDITIVE,
    )

    assert record.input_tokens is None
    assert record.output_tokens == 5
    assert record.total_tokens is None


def test_a_zero_count_is_kept_as_zero_because_it_is_a_real_value() -> None:
    record = normalize_usage_record(
        platform="opencode",
        provider_id="opencode",
        model_id="m",
        session_id="ses_1",
        message_id="msg_1",
        source_event_id="msg_1",
        timestamp=datetime(2026, 10, 10, tzinfo=timezone.utc),
        raw_tokens={"input": 0, "output": 0},
        relationships=ADDITIVE,
    )

    assert record.total_tokens == 0
    assert record.consumption_tokens == 0
    assert record.usage_status == "reported"


# --- rule 5: reported and estimated usage stay distinguishable ---


def test_a_record_with_counts_is_reported() -> None:
    assert resolve_usage_status(categories(input_tokens=10, output_tokens=5)) == "reported"


def test_a_record_with_no_counts_is_unavailable() -> None:
    assert resolve_usage_status(TokenCategories()) == "unavailable"


def test_an_estimated_record_is_marked_estimated() -> None:
    resolved = resolve_usage_status(categories(input_tokens=10), estimated=True)

    assert resolved == "estimated"


def test_an_estimate_with_nothing_to_estimate_from_is_unavailable() -> None:
    assert resolve_usage_status(TokenCategories(), estimated=True) == "unavailable"


# --- rules 6, 7, 8: overlap relationships and double counting ---


def test_additive_categories_are_excluded_from_the_per_call_total() -> None:
    """Rule 6 and 7: OpenCode adds cache and reasoning, so they are not inside input/output."""
    totals = calculate_totals(
        categories(input_tokens=100, output_tokens=20, reasoning_tokens=5, cache_read_tokens=900),
        ADDITIVE,
    )

    assert totals.total_tokens == 120
    assert totals.consumption_tokens == 1025


def test_consumption_sums_every_additive_category_once() -> None:
    totals = calculate_totals(
        categories(
            input_tokens=100,
            output_tokens=20,
            reasoning_tokens=5,
            cache_read_tokens=900,
            cache_write_tokens=3,
        ),
        ADDITIVE,
    )

    assert totals.consumption_tokens == 1028


def test_subset_categories_are_not_counted_twice() -> None:
    """Rule 8: a category already inside input must not be added again."""
    totals = calculate_totals(
        categories(input_tokens=100, output_tokens=20, reasoning_tokens=5, cache_read_tokens=900),
        SUBSET,
    )

    assert totals.consumption_tokens == 120


def test_the_relationship_is_reported_on_the_result() -> None:
    totals = calculate_totals(categories(input_tokens=1, output_tokens=1), ADDITIVE)

    assert totals.cache_overlap == "additive"
    assert totals.reasoning_overlap == "additive"


def test_cache_and_reasoning_never_inflate_the_per_call_total() -> None:
    totals = calculate_totals(
        categories(input_tokens=10, output_tokens=5, cache_read_tokens=1_000_000), ADDITIVE
    )

    assert totals.total_tokens == 15


# --- totals stay unknown rather than partial ---


def test_consumption_is_unknown_when_input_is_missing() -> None:
    assert sum_every_category(categories(output_tokens=5), ADDITIVE) is None


def test_consumption_ignores_unknown_secondary_categories_without_failing() -> None:
    """A missing reasoning count must not void a total we can otherwise compute."""
    totals = calculate_totals(categories(input_tokens=100, output_tokens=20), ADDITIVE)

    assert totals.consumption_tokens == 120


# --- raw metadata parsing ---


def test_the_cache_object_is_read_from_a_nested_key() -> None:
    parsed = token_categories_from_mapping(
        {"input": 1, "output": 2, "cache": {"read": 3, "write": 4}}
    )

    assert parsed.cache_read_tokens == 3
    assert parsed.cache_write_tokens == 4


def test_a_missing_cache_object_leaves_cache_unknown() -> None:
    parsed = token_categories_from_mapping({"input": 1, "output": 2})

    assert parsed.cache_read_tokens is None
    assert parsed.cache_write_tokens is None


# --- rule 9: raw metadata is preserved ---


def test_the_original_token_payload_is_preserved_verbatim() -> None:
    raw = {
        "total": 8297,
        "input": 6478,
        "output": 27,
        "reasoning": 0,
        "cache": {"read": 1792, "write": 0},
    }

    record = normalize_usage_record(
        platform="opencode",
        provider_id="opencode",
        model_id="big-pickle",
        session_id="ses_1",
        message_id="msg_1",
        source_event_id="msg_1",
        timestamp=datetime(2026, 10, 10, tzinfo=timezone.utc),
        raw_tokens=raw,
        raw_usage={"tokens": raw, "finish": "stop"},
        relationships=ADDITIVE,
    )

    assert record.raw_usage["tokens"] == raw
    assert record.raw_usage["finish"] == "stop"


def test_consumption_reproduces_the_providers_own_reported_total() -> None:
    """The real shape from OpenCode: 8297 total against 6478 input and 27 output."""
    record = normalize_usage_record(
        platform="opencode",
        provider_id="opencode",
        model_id="big-pickle",
        session_id="ses_1",
        message_id="msg_1",
        source_event_id="msg_1",
        timestamp=datetime(2026, 10, 10, tzinfo=timezone.utc),
        raw_tokens={
            "total": 8297,
            "input": 6478,
            "output": 27,
            "reasoning": 0,
            "cache": {"read": 1792, "write": 0},
        },
        relationships=ADDITIVE,
    )

    assert record.total_tokens == 6505
    assert record.consumption_tokens == 8297
