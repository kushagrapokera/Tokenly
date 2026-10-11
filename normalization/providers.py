"""Canonical provider identifiers and alias resolution, shared by every collector.

Phase 7 (Codex provider compatibility) needs the tracker's stable provider ids to
be defined once and reused, not re-invented per platform. This module is that
single source: the canonical ids the rest of the system stores and displays, an
alias map that folds known spellings onto them, and a gateway-prefix table for the
one case where a model string reliably names its provider.

Nothing here reads a credential, an env-var value, or a config value — provider
attribution is a pure function of non-secret identifiers (plan rule: avoid
credential collection).
"""

# The provider ids the rest of the system stores and displays. Claude Code already
# used these exact spellings; they are extracted here so Codex reuses them rather
# than defining a parallel set.
UNKNOWN = "unknown"
ANTHROPIC = "anthropic"
OPENROUTER = "openrouter"
BEDROCK = "bedrock"
VERTEX = "vertex"
DEEPSEEK = "deepseek"
GLM = "glm"
MOONSHOT = "moonshot"
OPENAI = "openai"
OLLAMA = "ollama"

# Aliases fold known spellings / vendor synonyms onto the canonical id. Keys are
# matched case-insensitively. These mirror the gateway conventions Claude Code
# already established (`zai` -> `glm`, `kimi` -> `moonshot`, ...). Anything not
# listed here is *preserved verbatim* by `canonicalize_provider` — an explicit
# `model_provider` is authoritative first-hand metadata even when we don't name it.
PROVIDER_ALIASES: dict[str, str] = {
    "anthropic": ANTHROPIC,
    "openrouter": OPENROUTER,
    "bedrock": BEDROCK,
    "vertex": VERTEX,
    "deepseek": DEEPSEEK,
    "glm": GLM,
    "zai": GLM,
    "z.ai": GLM,
    "zhipuai": GLM,
    "moonshot": MOONSHOT,
    "kimi": MOONSHOT,
    "moonshotai": MOONSHOT,
    "openai": OPENAI,
    "ollama": OLLAMA,
}

# Explicit gateway namespaces a model string may carry as `provider/model`. A
# prefix the user typed is the string's own provider namespace (analogous to
# Claude Code's rule 2), which is why it counts where a bare model *name* would
# only be a guess. Bare names (`deepseek-flash`, `gpt-4o`) are deliberately NOT
# inferred — see `provider_from_model_prefix`.
GATEWAY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("openrouter/", OPENROUTER),
    ("bedrock/", BEDROCK),
    ("vertex/", VERTEX),
    ("anthropic/", ANTHROPIC),
    ("deepseek/", DEEPSEEK),
    ("glm/", GLM),
    ("zai/", GLM),
    ("kimi/", MOONSHOT),
    ("moonshot/", MOONSHOT),
    ("openai/", OPENAI),
    ("ollama/", OLLAMA),
)


def canonicalize_provider(raw_provider: str | None) -> str | None:
    """Fold a recorded provider id onto its canonical spelling.

    A recognized alias maps to its canonical id. An unrecognized value is returned
    verbatim (not lowercased, not coerced to `unknown`) because it is real,
    first-hand provider metadata worth preserving. Returns None only for a missing
    or blank input, so callers can fall through to the next rule.
    """
    if raw_provider is None:
        return None
    stripped = raw_provider.strip()
    if not stripped:
        return None
    mapped = PROVIDER_ALIASES.get(stripped.lower())
    if mapped is not None:
        return mapped
    return stripped


def provider_from_model_prefix(model_id: str | None) -> str | None:
    """Return the provider a model string's explicit gateway prefix names.

    Only a `provider/` prefix counts; a bare model name is never inferred. Returns
    None when the model string carries no recognized gateway namespace.
    """
    if not model_id:
        return None
    lowered = model_id.lower()
    for prefix, provider in GATEWAY_PREFIXES:
        if lowered.startswith(prefix):
            return provider
    return None
