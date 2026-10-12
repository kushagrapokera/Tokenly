"""Token categories and the overlap relationship between them.

Phase 4 rule 6 and 7 ask whether cached tokens are already inside `input_tokens`, and
whether reasoning tokens are already inside `output_tokens`. The answer is provider
specific, so it is stated here as data rather than assumed.

Evidence gathered from the developer's own OpenCode database (OpenCode 1.18.35,
1,748 assistant messages) and recorded in `docs/opencode_storage_analysis.md`:

    total == input + output + reasoning + cache.read + cache.write

held on 1,415 of 1,415 records that carried a total. If cache reads were a subset of
input, or reasoning a subset of output, OpenCode would not have added them again. So on
OpenCode both are *additive*: separate categories on top of input and output, not
components inside them.

That is why `total_tokens` counts only input and output, while `consumption_tokens`
counts every category. Folding cache into the per-call total would report ~9.4M tokens
where the machine actually consumed ~128M, a 12x undercount.

Any future provider whose categories overlap differently must be given its own
relationship here rather than inheriting OpenCode's.
"""

from dataclasses import dataclass
from typing import Literal

CacheOverlap = Literal["additive", "subset_of_input"]
ReasoningOverlap = Literal["additive", "subset_of_output"]

# The two `cache_overlap` values, named so callers never compare against a bare string
# literal. `aggregation.cache` branches on SUBSET_OF_INPUT to pick its denominator.
ADDITIVE_CACHE: CacheOverlap = "additive"
SUBSET_OF_INPUT: CacheOverlap = "subset_of_input"


@dataclass(frozen=True)
class CategoryRelationships:
    """How a provider's secondary token categories relate to input and output."""

    cache_overlap: CacheOverlap = "additive"
    reasoning_overlap: ReasoningOverlap = "additive"


OPENCODE_RELATIONSHIPS = CategoryRelationships(
    cache_overlap="additive",
    reasoning_overlap="additive",
)


CLINE_RELATIONSHIPS = CategoryRelationships(
    cache_overlap="additive",
    reasoning_overlap="additive",
)


CLAUDE_RELATIONSHIPS = CategoryRelationships(
    cache_overlap="additive",
    # Anthropic reports thinking tokens inside output_tokens_details.thinking_tokens,
    # which is already part of output_tokens — a subset, never extra. Verified on the
    # live store: thinking_tokens was 0 on every assistant line while output was
    # non-zero, and the field proofs it is a breakdown of output rather than a
    # separate category (see docs/claude_storage_analysis.md §4).
    reasoning_overlap="subset_of_output",
)


CODEX_RELATIONSHIPS = CategoryRelationships(
    # Codex reports `cached_input_tokens` and `reasoning_output_tokens` inside its
    # six-field usage object, but its own `total_tokens` equals input + output and
    # never adds them again. Verified on every token_usage_record in the live store
    # (Codex CLI 0.155.1): `total == input + output`, `cached_input <= input`, and
    # `reasoning <= output` held on all 229 records — so both are subsets of
    # input/output, not additive categories on top of them (see
    # `docs/codex_storage_analysis.md` §4).
    cache_overlap="subset_of_input",
    reasoning_overlap="subset_of_output",
)
