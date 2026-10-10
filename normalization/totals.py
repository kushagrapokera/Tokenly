"""Turn a raw provider token payload into normalized, non-double-counted totals.

Phase 4's rules 6 to 8 live here:

  6. determine whether cached tokens overlap with input tokens
  7. determine whether reasoning tokens overlap with output tokens
  8. prevent overlapping categories from being counted twice

Two totals are produced because they answer different questions:

  `total_tokens`        input + output. What the call itself cost, comparable across
                        providers, and the figure `opencode stats` labels Input+Output.

  `consumption_tokens`  every category that was actually billed. On OpenCode this adds
                        reasoning and cache reads, which are additive rather than
                        subsets, so leaving them out would undercount ~12x.

Nothing is invented: a total is emitted only when every category it sums is known.
A partial sum is reported as unknown, not as a smaller number.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from normalization.categories import CategoryRelationships

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenCategories:
    """One record's token counts by category, before any overlap handling."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None

    @property
    def has_any_value(self) -> bool:
        """Report whether the source gave us at least one count."""
        return any(
            value is not None
            for value in (
                self.input_tokens,
                self.output_tokens,
                self.reasoning_tokens,
                self.cache_read_tokens,
                self.cache_write_tokens,
            )
        )

    @property
    def is_complete(self) -> bool:
        """Report whether input and output, the two categories a total is built from, are known."""
        return self.input_tokens is not None and self.output_tokens is not None


@dataclass(frozen=True)
class NormalizedTotals:
    """Totals derived from a record's token categories."""

    total_tokens: int | None
    consumption_tokens: int | None
    cache_overlap: str
    reasoning_overlap: str


def calculate_totals(
    categories: TokenCategories, relationships: CategoryRelationships
) -> NormalizedTotals:
    """Compute the per-call total and the true consumption total without double counting."""
    total_tokens = sum_input_and_output(categories)
    consumption_tokens = sum_every_category(categories, relationships)

    if categories.has_any_value and total_tokens is None:
        logger.debug(
            "input/output incomplete; leaving totals unknown rather than reporting a partial sum"
        )

    return NormalizedTotals(
        total_tokens=total_tokens,
        consumption_tokens=consumption_tokens,
        cache_overlap=relationships.cache_overlap,
        reasoning_overlap=relationships.reasoning_overlap,
    )


def sum_input_and_output(categories: TokenCategories) -> int | None:
    """Return input + output, or None when either is unknown."""
    if not categories.is_complete:
        return None
    assert categories.input_tokens is not None and categories.output_tokens is not None
    return categories.input_tokens + categories.output_tokens


def sum_every_category(
    categories: TokenCategories, relationships: CategoryRelationships
) -> int | None:
    """Return every non-overlapping category summed once.

    A category that is a *subset* of input or output is skipped: it is already counted
    there, and adding it again is exactly the double counting rule 8 forbids.
    """
    summands: list[int] = []

    for value, required in (
        (categories.input_tokens, True),
        (categories.output_tokens, True),
    ):
        if required and value is None:
            return None
        if value is not None:
            summands.append(value)

    if relationships.reasoning_overlap == "additive" and categories.reasoning_tokens is not None:
        summands.append(categories.reasoning_tokens)
    if relationships.cache_overlap == "additive":
        if categories.cache_read_tokens is not None:
            summands.append(categories.cache_read_tokens)
        if categories.cache_write_tokens is not None:
            summands.append(categories.cache_write_tokens)

    return sum(summands)


def token_categories_from_mapping(raw: Mapping[str, object]) -> TokenCategories:
    """Build categories from a raw token mapping, keeping unknowns as None."""
    cache = raw.get("cache")
    cache_mapping: Mapping[str, object] = cache if isinstance(cache, Mapping) else {}
    return TokenCategories(
        input_tokens=read_count(raw.get("input")),
        output_tokens=read_count(raw.get("output")),
        reasoning_tokens=read_count(raw.get("reasoning")),
        cache_read_tokens=read_count(cache_mapping.get("read")),
        cache_write_tokens=read_count(cache_mapping.get("write")),
    )


def read_count(value: object) -> int | None:
    """Return a nonnegative integer count, or None when the value is absent or unusable."""
    if value is None or isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value
