"""Phase 7 tests: Codex provider attribution — aliases, switching, and no guessing.

These pin the §5.3 priority (recorded `model_provider` > explicit gateway prefix >
`unknown`), the alias canonicalisation shared with Claude, and the two rules that
keep attribution honest: never infer a provider from a bare model name, and never
coerce an unrecognised provider to `unknown`.
"""

from collectors.codex import CodexCollector
from collectors.codex.providers import resolve_provider_id
from config.settings import Settings
from normalization.providers import (
    DEEPSEEK,
    GLM,
    MOONSHOT,
    OPENROUTER,
    UNKNOWN,
    canonicalize_provider,
    provider_from_model_prefix,
)
from tests.collectors.codex.conftest import CodexStoreBuilder


def collector_for(store: CodexStoreBuilder) -> CodexCollector:
    return CodexCollector(Settings(codex_home=store.codex_home))


# --- resolve_provider_id: §5.3 priority ---


def test_a_recorded_provider_is_used_verbatim_when_canonical() -> None:
    assert resolve_provider_id("deepseek", "deepseek-flash") == DEEPSEEK


def test_a_recorded_alias_is_folded_onto_the_canonical_id() -> None:
    assert resolve_provider_id("zai", "glm-4") == GLM
    assert resolve_provider_id("kimi", "kimi-k2") == MOONSHOT
    assert resolve_provider_id("Z.AI", "glm-4") == GLM  # case-insensitive


def test_an_unrecognised_provider_is_preserved_not_coerced_to_unknown() -> None:
    assert resolve_provider_id("mycompany", "some-model") == "mycompany"
    assert resolve_provider_id("MyGateway", "some-model") == "MyGateway"


def test_an_absent_provider_falls_back_to_an_explicit_gateway_prefix() -> None:
    assert resolve_provider_id(None, "openrouter/llama-3") == OPENROUTER
    assert resolve_provider_id(None, "glm/glm-4-air") == GLM


def test_a_bare_model_name_is_never_inferred_as_a_provider() -> None:
    """The banned inference: a name alone through an unnamed gateway stays unknown."""
    assert resolve_provider_id(None, "deepseek-flash") == UNKNOWN
    assert resolve_provider_id(None, "gpt-4o") == UNKNOWN
    assert resolve_provider_id(None, "kimi-k2") == UNKNOWN


def test_a_blank_provider_falls_through_to_the_next_rule() -> None:
    assert resolve_provider_id("   ", "openrouter/llama-3") == OPENROUTER
    assert resolve_provider_id("", "deepseek-flash") == UNKNOWN


# --- shared canonicalisation primitives ---


def test_canonicalize_provider_returns_none_only_for_missing_or_blank() -> None:
    assert canonicalize_provider(None) is None
    assert canonicalize_provider("  ") is None


def test_canonicalize_preserves_an_unknown_value_verbatim() -> None:
    assert canonicalize_provider("MyCustomProvider") == "MyCustomProvider"


def test_provider_from_model_prefix_matches_gateways_and_ignores_bare_names() -> None:
    assert provider_from_model_prefix("openrouter/meta-llama") == OPENROUTER
    assert provider_from_model_prefix("deepseek/deepseek-chat") == DEEPSEEK
    assert provider_from_model_prefix("deepseek-flash") is None
    assert provider_from_model_prefix(None) is None


# --- end-to-end through the collector ---


def test_model_switching_across_turns_is_preserved(codex_store: CodexStoreBuilder) -> None:
    codex_store.start_session(session_id="s-switch", model_provider="openai")
    codex_store.add_turn_context(turn_id="t1", model="gpt-4o", session_id="s-switch")
    codex_store.add_usage_call(session_id="s-switch", turn_id="t1", write_turn_context=False)
    codex_store.add_turn_context(turn_id="t2", model="o4-mini", session_id="s-switch")
    codex_store.add_usage_call(session_id="s-switch", turn_id="t2", write_turn_context=False)

    records = collector_for(codex_store).collect_history()

    assert {record.model_id for record in records} == {"gpt-4o", "o4-mini"}
    # Provider is per-session metadata, so it stays openai across both models.
    assert {record.provider_id for record in records} == {"openai"}


def test_provider_switching_across_sessions_is_preserved(
    codex_store: CodexStoreBuilder,
) -> None:
    codex_store.start_session(session_id="s-deep", model_provider="deepseek")
    codex_store.add_usage_call(session_id="s-deep", turn_id="t-deep")
    codex_store.start_session(session_id="s-open", model_provider="openai")
    codex_store.add_usage_call(session_id="s-open", turn_id="t-open")

    records = collector_for(codex_store).collect_history()

    assert {record.provider_id for record in records} == {"deepseek", "openai"}


def test_an_alias_provider_is_canonicalised_through_the_whole_collector(
    codex_store: CodexStoreBuilder,
) -> None:
    codex_store.start_session(session_id="s-alias", model_provider="zai")
    codex_store.add_usage_call(session_id="s-alias", turn_id="t-alias")

    records = collector_for(codex_store).collect_history()

    assert {record.provider_id for record in records} == {GLM}


def test_a_session_without_provider_metadata_uses_the_model_gateway_prefix(
    codex_store: CodexStoreBuilder,
) -> None:
    codex_store.start_session(session_id="s-prefix", model_provider=None)
    codex_store.add_turn_context(turn_id="t-prefix", model="glm/glm-4-air", session_id="s-prefix")
    codex_store.add_usage_call(session_id="s-prefix", turn_id="t-prefix", write_turn_context=False)

    records = collector_for(codex_store).collect_history()

    assert len(records) == 1
    assert records[0].provider_id == GLM
    assert records[0].model_id == "glm/glm-4-air"  # original model id preserved


def test_an_unrecognised_provider_survives_the_whole_collector(
    codex_store: CodexStoreBuilder,
) -> None:
    codex_store.start_session(session_id="s-custom", model_provider="mycompany")
    codex_store.add_usage_call(session_id="s-custom", turn_id="t-custom")

    records = collector_for(codex_store).collect_history()

    assert {record.provider_id for record in records} == {"mycompany"}
