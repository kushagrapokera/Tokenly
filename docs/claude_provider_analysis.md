# Claude Code Provider Compatibility (Phase 4 Deliverable)

How Claude Code usage is attributed to the platform's providers, for native and
third-party configurations, verified live where data exists and by documented
id shapes where it does not. Companion to `docs/claude_storage_analysis.md`
(§5 is superseded in part by this document's rules).

Exit criterion (implementation.md Phase 4): *Claude Code usage is attributed to
the correct platform, known gateway/provider, and model without requiring
credentials.*

## 1. What Claude Code records (and what it does not)

Assistant lines record only `message.model` — a plain string the user or a
router configured. There is **no provider field, no base-URL field, no
account field** in the transcript lines. The session-level `cost-state` lines
carry per-model `modelUsage` rollups (cross-check only, never collected).

Consequence: per-request provider attribution has exactly one first-class
signal — the model string itself — plus non-secret configuration evidence
which is session-invariant and therefore cannot attribute per request.

## 2. Detection rules (in the order implemented)

Implemented in `collectors/claude/providers.py::infer_provider_id`; each rule
cited to the plan's Phase 4 numbering:

| # | Rule | Source | Example → provider |
|---|---|---|---|
| R1 | Explicit gateway prefix in the model string | the user's own namespace (`openrouter/deepseek/deepseek-chat`) | `openrouter/...` → openrouter, `deepseek/...` → deepseek, `kimi/...`/`moonshot/...` → moonshot, `zai/...`/`glm/...` → glm, `openai/...` → openai, `ollama/...` → ollama, plus bedrock/vertex/anthropic prefixes |
| R2a | Documented Amazon Bedrock model-ID shape | AWS docs (`anthropic.claude-…-vN:0`) | `anthropic.claude-sonnet-4-5-v1:0` → bedrock |
| R2b | Documented Bedrock regional inference-profile prefix | AWS docs (`us.`/`eu.`/`apac.` + `anthropic.…`) | `eu.anthropic.claude-…-v1:0` → bedrock |
| R2c | Documented Vertex AI published-version shape | Google docs (`claude-…@YYYYMMDD`) | `claude-sonnet-4-5@20250514` → vertex |
| R3 | Non-secret configuration metadata | session-invariant; cannot attribute per request in this iteration | (see §4) |
| R4 | **Never from a bare model name** | plan §4.3 | `deepseek-flash`, `kimi-k2`, `claude-sonnet-4-5` → `unknown` |
| R5 | Preserve unknowns | plan §4.3 | anything else → `unknown` |

Rule order is load-bearing: a user-typed prefix wins over a coincidental
shape match (`bedrock/claude-sonnet-4-5@20250514` is OpenRouter's id, not
Vertex's), and the Vertex `@` check requires a `claude-` base with a numeric
version head so `gpt-4.1@20250514` or `claude-4@latest` are not misread.

Live validation: this machine's store holds one bare gateway model
(`deepseek-flash`), which correctly stays `unknown` — proof that gateway usage
without an explicit prefix exists in practice and that R4's honesty rule is
exercised against real records, not just fixtures.

## 3. Model identity

Model ids are preserved verbatim (`openrouter/deepseek/deepseek-chat` is not
re-named to `deepseek-chat`, per §6.1's preserve-identifiers rule). Version
distinctions survive: Anthropic SDK ids, Bedrock `:0` revisioned ids, and
Vertex dated versions remain distinguishable because the string is intact.

Model switching: attribution is per model request (`message.id`), so switches
inside a session need no session-level handling — tested in
`tests/integration/test_claude_providers.py`.

## 4. Configuration evidence — deliberately deferred

`ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN`-style settings can prove
first-party vs gateway routing at the *session* level, but:
reading env-var names requires opening settings files this iteration does not
need (R1–R2 already cover every configuration with an explicit signal), and
the stored `raw_usage` keeps the room to add that evidence later without a
migration. Deferred as YAGNI; the extraction point is
`read_raw_usage` in `collectors/claude/extractor.py`.

Credential rule honored: nothing in this phase reads any env-var *value*,
settings value, or key material (plan §12).

## 5. Test coverage

| Requirement | Test |
|---|---|
| Prefix rules for every target provider | `tests/collectors/claude/test_providers.py` (parametrized) |
| Bedrock native + regional shapes | same, `test_bedrock_native_model_ids…` |
| Vertex published-version shape + negatives | same |
| Bare names stay unknown (R4) | `test_native_first_party_names_are_not_assumed`, `test_a_bare_third_party_name_is_unknown` |
| Attribution flows through the extractor | `test_extracted_provider_matches_the_inferred_one` |
| Provider switching mid-session | `test_provider_switching_within_one_session_splits_the_breakdown` |
| Same model via two gateways stays distinct | `test_the_same_model_through_two_gateways_stays_distinct` |
| Missing model metadata | `test_missing_model_metadata_is_counted_under_the_unknown_model` |
| Provider totals reconcile | `test_provider_totals_reconcile_with_the_platform_summary` |

## 6. Limitations

- Live stores obtainable on this machine contain only bare gateway model
  names, so R1/R2 shapes are verified against vendor documentation and
  fixtures, not saturating live rows. The learning tests will surface drift
  when such data exists (`docs/claude_storage_analysis.md` §11's rule).
- Fewer-shaped gateways (first-party Anthropic `claude-*` bare names routed
  through an invisible proxy) cannot be distinguished from direct usage at
  the transcript level at all; they are recorded `unknown` by design — the
  plan's "avoid incorrect attribution" rule outranks coverage here.
