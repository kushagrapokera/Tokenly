"""Provider attribution for Claude Code usage.

Phase 4's rules live here, stated once in the order the plan fixes them
(`docs/implementation.md` Phase 4 "Provider Detection Rules"):

1. **Prefer explicit provider metadata.** Claude Code records none in its
   assistant lines, so rule 1 usually passes to the rules below.
2. **Use documented non-secret configuration metadata when reliable.** Two
   shapes are documented by their vendors and appear verbatim in the model
   string: Amazon Bedrock's `anthropic.claude-...` model IDs and Google
   Vertex AI's `claude-...@<date>` published IDs. A prefix the user typed
   (`openrouter/...`) is the model string's own provider namespace.
3. **Never inspect credential values.** Nothing here reads keys, tokens, or
   env-var *values* — the raw env-var-name evidence recorded by the reader
   is already non-secret.
4. **Never assume the provider from a model name alone.** A bare
   `deepseek-flash` or `kimi-k2` reaches Claude Code through an unnamed
   gateway; attributing it to the model's developer would be a guess.
5. **Preserve unknown values.** When no reliable signal exists the answer is
   `unknown`, shown honestly by the dashboard rather than invented.

The returned identifiers are the tracker's stable provider ids; they join
`(platform, provider_id, model_id)` in every breakdown.
"""

from normalization.providers import BEDROCK, GATEWAY_PREFIXES, VERTEX
from normalization.providers import UNKNOWN as UNKNOWN_PROVIDER

# The canonical provider ids and the gateway-prefix table are shared with the other
# collectors (`normalization/providers.py`); Claude-specific prefix/id-shape inference
# lives below and is not reused by Codex, which has first-class provider metadata.

# Gateway prefixes: `provider/model` as the user typed it into their router
# or model setting. Checked before the id-shape rules so an explicit
# namespace wins over a coincidental shape match.

# Documented Bedrock model-ID shapes: `anthropic.claude-...` and the regional
# inference-profile forms `us.`, `eu.`, `apac.` + `anthropic.claude-...`
# (AWS Bedrock Model IDs documentation; the region-system prefix precedes the
# vendor dot on cross-region profiles).
_BEDROCK_VENDOR_DOT = "anthropic."
_BEDROCK_REGION_PREFIXES = ("us.", "eu.", "apac.")

# Documented Vertex AI model-version shape: `claude-<name>@<YYYYMMDD>`
# (Google Vertex "Model versions for Claude"; the @-version marks Vertex's
# published model versions, a shape no other documented provider uses).
_VERTEX_VERSION_SEPARATOR = "@"


def infer_provider_id(model_id: str) -> str:
    """Return the provider a Claude Code model string reliably names.

    Order matters and mirrors the plan's rules: an explicit prefix wins,
    then the two documented id shapes, then native first-party naming, and
    everything else stays `unknown`. No other source is consulted, so the
    function is a pure function of the model string — easy to test and free
    of credential inspection (rule 3).
    """
    lowered = model_id.lower()

    for prefix, provider in GATEWAY_PREFIXES:
        if lowered.startswith(prefix):
            return provider

    if lowered.startswith(_BEDROCK_VENDOR_DOT) or _is_regional_bedrock(lowered):
        return BEDROCK

    if _is_vertex_versioned(lowered):
        return VERTEX

    return UNKNOWN_PROVIDER


def _is_regional_bedrock(lowered_model_id: str) -> bool:
    """Report whether the id is a regional Bedrock inference-profile id."""
    for region_prefix in _BEDROCK_REGION_PREFIXES:
        if lowered_model_id.startswith(region_prefix):
            remainder = lowered_model_id[len(region_prefix) :]
            return remainder.startswith(_BEDROCK_VENDOR_DOT)
    return False


def _is_vertex_versioned(lowered_model_id: str) -> bool:
    """Report whether the id matches Vertex's documented `name@date` shape."""
    base, separator, version = lowered_model_id.partition(_VERTEX_VERSION_SEPARATOR)
    return bool(separator) and base.startswith("claude-") and version[:1].isdigit()
