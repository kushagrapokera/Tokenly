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
