"""Phase 4 — provider attribution rules for Claude Code model strings.

The rules and their order are asserted from `collectors/claude/providers.py`,
whose docstring cites them. Two require live data this machine does not
produce (Bedrock's `anthropic.claude-*` ids, Vertex's `claude-*@20250514`
versions); their *shapes* are those vendors' documented model-ID formats
(asserted as pure-function behavior here) and the learning hooks in
`test_learning_tests.py` will catch drift when such a store is available.
"""

import pytest

from collectors.claude.extractor import extract_usage_record, infer_provider_id
from collectors.claude.providers import (
    ANTHROPIC,
    BEDROCK,
    DEEPSEEK,
    GLM,
    MOONSHOT,
    OLLAMA,
    OPENAI,
    OPENROUTER,
    UNKNOWN_PROVIDER,
    VERTEX,
)
from tests.collectors.claude.conftest import ClaudeStoreBuilder

# Explicit prefix rules -------------------------------------------


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("openrouter/deepseek/deepseek-chat", OPENROUTER),
        ("bedrock/us.anthropic.claude-sonnet-4-5-v1:0", BEDROCK),  # user-typed prefix
        ("vertex/claude-sonnet-4-5@20250514", VERTEX),
        ("anthropic/claude-sonnet-4-5", ANTHROPIC),
        ("deepseek/deepseek-chat", DEEPSEEK),
        ("glm/glm-5.2", GLM),
        ("zai/glm-5.2", GLM),
        ("kimi/kimi-k2-thinking", MOONSHOT),
        ("moonshot/kimi-k2", MOONSHOT),
        ("openai/gpt-5.2-codex", OPENAI),
        ("ollama/llama3:8b", OLLAMA),
    ],
)
def test_gateway_prefixes_name_the_provider(model_id: str, expected: str) -> None:
    assert infer_provider_id(model_id) == expected


def test_prefixes_are_case_insensitive() -> None:
    assert infer_provider_id("OpenRouter/deepseek/deepseek-chat") == OPENROUTER


# Documented id shapes (rule 2) -----------------------------------


def test_bedrock_native_model_ids_name_the_provider() -> None:
    # Amazon Bedrock's documented model-ID format for Claude models, as
    # recorded by `ANTHROPIC_MODEL` values like the AWS docs' examples.
    assert infer_provider_id("anthropic.claude-sonnet-4-5-v1:0") == BEDROCK
    assert infer_provider_id("anthropic.claude-opus-4-6-v1:0") == BEDROCK
    # A regional Bedrock inference profile id keeps the same vendor prefix.
    assert infer_provider_id("eu.anthropic.claude-sonnet-4-5-20250929-v1:0") == BEDROCK


def test_vertex_published_model_versions_name_the_provider() -> None:
    # Google Vertex AI's documented `claude-*@YYYYMMDD` published versions.
    assert infer_provider_id("claude-sonnet-4-5@20250514") == VERTEX
    assert infer_provider_id("claude-opus-4-6@20260201") == VERTEX
    # The exact-prompt variant Vertex documents (`@-version` minus date) is
    # still the published-versions namespace.
    assert infer_provider_id("claude-sonnet-4-5@2.1") == VERTEX


def test_the_version_marker_alone_is_not_vertex() -> None:
    # The `@` only means Vertex on a `claude-` base: not on other bases,
    # not with a non-numeric version head, not without one.
    assert infer_provider_id("gpt-4.1@20250514") != VERTEX
    assert infer_provider_id("claude-sonnet-4-5@latest") != VERTEX


# Native first-party models stay recordable but unknown-gateway ----------


def test_native_first_party_names_are_not_assumed() -> None:
    # Rule 4: a bare `claude-...` name could have arrived through any gateway;
    # without an explicit signal the provider stays unknown. This store's own
    # `deepseek-flash` records are the live proof that gateway usage exists.
    assert infer_provider_id("claude-sonnet-4-5") == UNKNOWN_PROVIDER
    assert infer_provider_id("claude-opus-4-6") == UNKNOWN_PROVIDER


def test_a_bare_third_party_name_is_unknown() -> None:
    assert infer_provider_id("deepseek-flash") == UNKNOWN_PROVIDER
    assert infer_provider_id("kimi-k2") == UNKNOWN_PROVIDER
    assert infer_provider_id("glm-5.2") == UNKNOWN_PROVIDER
    assert infer_provider_id("gpt-5.1") == UNKNOWN_PROVIDER


def test_the_empty_string_is_unknown() -> None:
    assert infer_provider_id("") == UNKNOWN_PROVIDER


# Attribution flows through the whole extractor --------------------


def test_extracted_provider_matches_the_inferred_one(
    claude_store: ClaudeStoreBuilder,
) -> None:
    claude_store.add_assistant_request(
        message_id="m-bedrock1",
        model="anthropic.claude-sonnet-4-5-v1:0",
        line_count=1,
    )
    claude_store.add_assistant_request(
        message_id="m-bare0002", model="deepseek-flash", line_count=1
    )

    from collectors.claude.locator import resolve_projects_directory
    from collectors.claude.reader import SessionFile, iter_assistant_records
    from config.settings import Settings

    settings = Settings(claude_data_dir=claude_store.projects_dir.parent, log_level="WARNING")
    projects = resolve_projects_directory(settings)
    session = next(iter(projects.glob("*/*.jsonl")))
    session_file = SessionFile(
        session_id=session.stem, project_directory=session.parent.name, path=session
    )
    records = [
        extract_usage_record(assistant)
        for assistant in iter_assistant_records(session_file)
    ]

    by_model = {record.model_id: record for record in records if record is not None}
    assert by_model["anthropic.claude-sonnet-4-5-v1:0"].provider_id == BEDROCK
    assert by_model["deepseek-flash"].provider_id == UNKNOWN_PROVIDER
