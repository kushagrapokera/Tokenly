"""Provider attribution for Codex CLI usage (Phase 7).

Unlike Claude Code, Codex records a first-class provider id, so attribution is
driven by that metadata rather than guessed from a model's name. The order below
mirrors `docs/codex_storage_analysis.md` §5.3 and the Phase 7 requirements
(`docs/implementation.md`):

1. **`session_meta.model_provider`** — authoritative when present. Folded onto the
   canonical provider id via the shared alias map; an unrecognized value is
   preserved verbatim because it is real, first-hand metadata even when the tracker
   does not recognise the name.
2. **An explicit gateway prefix on the model string** (`openrouter/…`, `glm/…`)
   when no provider metadata exists. A prefix the user typed is a reliable
   namespace — not the banned "infer the provider from a bare model name" (`gpt-4o`
   or `deepseek-flash` through an unnamed gateway stays `unknown`).
3. **Otherwise `unknown`**, honestly represented rather than invented.

Nothing here reads a credential, an env-var value, or a `config.toml` value — only
the non-secret provider id Codex already wrote to `session_meta` (plan rule:
avoid credential collection).
"""

from normalization.providers import (
    UNKNOWN,
    canonicalize_provider,
    provider_from_model_prefix,
)


def resolve_provider_id(model_provider: str | None, model_id: str | None) -> str:
    """Return the provider id for one usage event, following §5.3's priority."""
    canonical = canonicalize_provider(model_provider)
    if canonical is not None:
        return canonical

    prefixed = provider_from_model_prefix(model_id)
    if prefixed is not None:
        return prefixed

    return UNKNOWN
