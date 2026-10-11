# Claude Code Storage Analysis (Phase 2 Deliverable)

Verified against Claude Code **2.1.278 / 2.1.282** on Linux, using the live local
store in `~/.claude/`. All reads were performed against an `/tmp` file copy
(`cp -r ~/.claude/projects /tmp/claude-readonly-copy`); the live store was never
written to and no prompt or response text was extracted. Counts reflect the store
as observed on 2026-10-12 (3 project dirs, 11 session files, 165 assistant lines,
58 distinct model requests).

Companion to `docs/opencode_storage_analysis.md` and `docs/cline_storage_analysis.md`.
This is the field map the Phase 3 collector must implement.

## 1. Verified storage locations

| Path | Purpose |
|---|---|
| `~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl` | **Authoritative usage.** One JSONL file per session; project dirs are the cwd with `/`→`-`. |
| `~/.claude/history.jsonl` | Prompt history index (`display`, `project`, `sessionId`, `timestamp`). Discovery aid / cross-check only — no token usage. |
| `~/.claude/settings.json`, `settings.local.json` | User settings. No usage data; never read for provider creds. |
| `~/.claude/backups/`, `cache/`, `plugins/`, `session-env/`, `shell-snapshots/`, `sessions/`, `ide/` | Not usage sources. |
| `~/.claude.json` (home dir, not observed here) | Legacy/global Claude state. Off-limits (may contain OAuth account info). |

Data dir overrides: `CLAUDE_CONFIG_DIR` has been observed in the wild and rewrites
`~/.claude` wholesale. The locator must resolve: explicit setting → `CLAUDE_CONFIG_DIR`
→ platform default `~/.claude`, logging any fallback. Linux verified; macOS (`~/.claude`)
and Windows (`%USERPROFILE%\.claude`) follow the same home-relative layout per upstream
docs and are unverified on those platforms — resolve at runtime, never hardcode.

Custom-provider configs: provider attribution (§5.3) is derived from the model
identifier string pattern and optionally from non-secret `settings.json` env-var
*names* only — never their values. Credential values are never read (plan §12).

## 2. Supported storage formats

JSONL only in the installed version. One file per session, one JSON object per line.
Line types observed (with counts across 11 files):

```
mode:40  permission-mode:40  file-history-snapshot:15  user:121  atis-latch:35
attachment:117  assistant:165  system:16  last-prompt:37  cost-state:11  ai-title:29
```

Only `type == "assistant"` lines carry model usage. `user` lines never carry a
`message.usage` object (verified 0/121) — so role-based filtering is not even needed;
type-based filtering alone is exact.

Session→file linkage: the filename stem equals the `sessionId` on every line
(verified on all 11 files). A session never spans multiple files in this store
(verified: 11 sessions, 0 spanning).

Version drift: files in this store are from two versions (2.1.278 and 2.1.282);
the `message`/`usage` shapes are identical across both. Learning tests must pin
these shapes so an upgrade that changes them fails fast in tests.

## 3. Relevant data structures

Assistant line (usage event):

```json
{ "parentUuid": "...", "isSidechain": false,
  "message": {
    "id": "6a40154b-24ac-4fb7-9a44-58dcd7ee8ea2",
    "type": "message", "role": "assistant", "model": "deepseek-flash",
    "content": [{"type": "text", "text": "..."}],
    "stop_reason": "end_turn",
    "usage": { "input_tokens": 20491, "output_tokens": 11,
               "cache_creation_input_tokens": 0,
               "cache_read_input_tokens": 0,
               "output_tokens_details": {"thinking_tokens": 0},
               "cache_creation": {"ephemeral_1h_input_tokens": 0,
                                   "ephemeral_5m_input_tokens": 0},
               "service_tier": "standard", "speed": "standard" }
  },
  "apiBlockIndex": 0, "type": "assistant",
  "uuid": "63dbe81a-ee45-436e-8fe7-97d4b1ee2c29",
  "timestamp": "2026-09-22T11:52:31.580Z",
  "sessionId": "0d55869d-c59f-44ec-bdd5-fde7d17756ef",
  "version": "2.1.278" }
```

Content block types observed: `{thinking, text, tool_use}` (58/15/92) — never read
as text; block types may be recorded in `raw_usage` for diagnostics (same privacy
posture as the Cline extractor).

Other line types (`cost-state`, `system`, `user`, …) are never collected. `cost-state`
carries a session-level `modelUsage` rollup — cross-check only (§7).

## 4. Token field definitions (authoritative source)

**Authoritative record = one assistant line, fields from `message.usage`:**

| Source field | Meaning | Non-zero rows (n=165) |
|---|---|---|
| `input_tokens` | Non-cached prompt tokens | 165/165 (min 168, max 25,813) |
| `output_tokens` | Completion tokens | 165/165 (min 11, max 5,005) |
| `cache_read_input_tokens` | Prompt tokens served from cache | 149/165 (max 115,200) |
| `cache_creation_input_tokens` | Prompt tokens written to cache | 0/165 (always 0 here) |
| `output_tokens_details.thinking_tokens` | Reasoning tokens inside output | 0/165 (always 0) |
| `cache_creation` (object) | Split of cache writes by 1h/5m TTL | sums = `cache_creation_input_tokens` on every row |

Field map: `input_tokens` → `input_tokens`, `output_tokens` → `output_tokens`,
`cache_read_input_tokens` → `cache_read_tokens`, `cache_creation_input_tokens`
(+ optional `cache_creation.ephemeral_*` detail) → `cache_write_tokens`,
`output_tokens_details.thinking_tokens` → `reasoning_tokens`.

There is **no reported total.** The collector computes `total = input + output` via
the shared `calculate_totals`; `consumption_tokens` adds additive categories per the
platform relationships.

**Cache overlap (validated):** Anthropic's semantics are `input_tokens` EXCLUDES
cache reads/writes — unlike OpenCode's additive layout. With
`cache_overlap="additive"` per platform, these are separate categories; and
`convert_to_dict` gets them right by construction since we store them in separate
columns and only sum into `consumption_tokens` under `CLAUDE_RELATIONSHIPS =
CategoryRelationships(cache_overlap="additive", reasoning_overlap="subset_of_output")`.
Distinct (in, out, cache_read, cache_write) combos: 58 in 165 lines — zero evidence
of any record where cache reads are already inside `input_tokens`. The plan's
"cache served from cache must not be omitted" rule is satisfied: cache reads land
in `consumption_tokens` and `cache_read_tokens` without inflating the per-call
`total_tokens`.

## 5. Model and provider identification

### 5.1 Model

- `message.model` is a plain string. This store: `"deepseek-flash"` (165/165).
- The session envelope's last model is NOT separately recorded. Per-message
  attribution is exact by construction.
- No model-switch evidence exists locally (1 distinct model across all sessions);
  per-message `model` handles switching without schema change (same posture as
  OpenCode/Cline docs).

### 5.2 Third-party model routing (validated live)

This store's `deepseek-flash` proves: **model developers other than Anthropic
can drive Claude Code.** `message.model` is what Claude Code itself used —
attribution must stay at the model level; the provider is a separate axis.

### 5.3 Provider

No first-class provider identifier exists in assistant lines. Reliable inference,
in priority order:

1. **Model-identifier prefixes** for known gateways, applied to the model string
   only: `openrouter/...` → OpenRouter, `bedrock/...` → Amazon Bedrock,
   `vertex/...`/`google-vertex-...` → Google Vertex AI, `deepseek/...` →
   DeepSeek, `glm/...`/`zai/...` → GLM (Z.AI), `kimi/...`/`moonshot/...` →
   Moonshot AI, `openai/...`/`gpt-...` → OpenAI-compatible routing.
   This store's bare `deepseek-flash` (no prefix) is NOT attributable to a named
   gateway with confidence — record `unknown`, per the plan's "preserve unknown"
   rule (§4.3 / §11: avoid incorrect attribution).
2. **Non-secret `settings.json` `env` keys** (names only, e.g. `ANTHROPIC_BASE_URL`
   or `CLAUDE_CODE_MAX_MODEL_IDS` presence) can distinguish Anthropic-first-party
   from gateway configurations, but are session-invariant and cannot attribute
   per-request. NEVER read the values.
3. Everything else → `"unknown"`, honestly represented, never guessed from model names.

This matches plan §4.3's "preserve unknown provider values when identification is
not reliable."

## 6. Timestamps

Every assistant line carries `timestamp` — ISO-8601 UTC with milliseconds
(`2026-09-22T11:52:31.580Z`). All 165 assistant lines have it. Range observed:
2026-09-22 → 2026-09-25.

`line.timestamp` is the usage event's timestamp, normalized via the shared
`normalize_timestamp`. It is stable across re-reads of the same line.

## 7. Streaming, repeated message records, and cumulative counters

**Critical finding — repeated message records (validated on all 165 lines):**

Claude Code writes **multiple JSONL lines per model request.** Each line is a
different `apiBlockIndex` of the same `message.id` (a request's content blocks
land as separate lines for streaming). Dedup multiplicities over the 58 distinct
ids: `x2: 28, x3: 17, x4: 9, x5: 3, x7: 1`.

- Usage values are **identical** across all lines of one `message.id`
  (verified: 58/58 duplicated ids have identical usage tuples).
- Timestamps differ slightly between lines of one id (streaming-write timing),
  so the first occurrence's timestamp is the event's timestamp.
- `uuid` (the line identity, 165 distinct of 165 lines) is NOT the usage event
  identity; `message.id` is.

**Dedup rule (only option consistent with Claude Code's own accounting):**
dedup on `(session_id, message.id)`, keeping one record per model request.
Claude Code's own session-level `modelUsage` rollup in its `cost-state` line
confirms this: for two small sessions it matches the distinct-id sums exactly
(`0d55869d`, `53f306ff`, `e938bbb5` — all MATCH:True), and for the larger
sessions (`afe0db6c`, `30c7dad5`) the mismatch exists only because `cost-state`
snapshots are cumulative-per-time snapshots taken mid-session, not final sums
(the session's `.jsonl` grows after the last `cost-state` was flushed). Line-level
sums triple-count (165-line global sum: in=611,611, out=149,542 vs 205,518/50,131
distinct — a ~3x overcount exactly matching the 2.84 avg multiplicities).

**Cumulative counter rule:** there is no cumulative counter inside assistant lines
(`cache_state`'s session-level `modelUsage` in `cost-state` lines is a mid-session
snapshot for cost display, NOT for collector aggregation — reading it as usage
inflates by counting a rolling snapshot). Per plan §5.4 ("cumulative totals must
not be counted as independent requests"), only `message.id`-distinct records are
collected. `cost-state` lines are never collected.

## 8. Session compaction, retries, subagents, resumed sessions

- **Retries/multi-GB streams of one request:** handled by the dedup rule in §7 —
  retries update the same `message.id` (line count grew to x7 in the largest
  example without a second id).
- **Subagents (`isSidechain: true`):** 0/165 in this store (all `false`). Subagent
  sessions exist upstream in newer versions; the collector must attribute by
  per-message `model` (already planned) so their usage lands correctly, and must
  not skip sidechain lines' usage — the tokens are real model calls.
- **Model switching:** not locally observed (1 model), but per-message handling is
  structural (§5.1).
- **Resumed/forked sessions:** `sessionId` equals the file stem on every line, and
  sessions never span files. A resumed session that Claude Code writes to a new
  file (new `sessionId`) with copied history lines will store per that session's
  id — the namespaced `{session_id}:{message.id}` key makes those copies distinct
  rows (the Cline §9 pattern, see also Phase 1 §4.1's pinned convention).
- **Compaction:** no `summary`/compaction markers in this store. Like OpenCode,
  nothing is ever deleted; vanished rows keep their placed rows in the tracker DB.

## 9. Incomplete or missing usage

All 165 assistant lines carry a complete `message.usage` object (no partial or
missing usage observed). Rules for robustness:

- `message.usage` missing/None → `usage_status="unavailable"`, all counts NULL,
  never zero.
- Present but zero fields → `"reported"` with the zeros (a reported zero is data).
- A line whose type is `assistant` but whose `message.role != "assistant"` → skip
  (defensive; matches upstream schema).
- Missing `message.id`/`model`/`timestamp` → skip the line with a warning, as the
  OpenCode reader does for malformed rows; a single bad line must not abort a
  whole import.

## 10. Free-model and paid availability

This store has no free/paid distinction beyond `service_tier: "standard"` on all
165 lines — `message.usage` is always present and complete regardless of tier
(AWS/Bedrock/OpenRouter/GLM/Kimi/first-party all flow through the same field set).
The tracker does not depend on billing state.

## 11. Cross-version compatibility

Files from 2.1.278 and 2.1.282 share the same `message`/`usage`/`timestamp` shapes
(verified field-by-field). The learning tests must pin: line types, assistant-line
keyset, `usage` keyset with the 4 token ints + details object + `cache_creation`
object, and the `{uuid, timestamp, sessionId, isSidechain}` framing — so a future
upgrade that changes any of them fails in tests, not in totals.

## 12. Privacy

- Only `type="assistant"` lines are read; content blocks are never decoded beyond
  the `type` field (no prompt/response/tool text is extracted).
- `history.jsonl` (prompts!) and `~/.claude.json` are never read in full; the
  collector reads only `<session-uuid>.jsonl` files inside `projects/`.
- No API keys read anywhere; `settings.json` may be opened for non-secret env-var
  *names* only, if provider inference needs it (§5.3.2), and values are never read.
- The tracker DB stores only the fields in §4's map + identifiers + raw JSON of the
  usage object (not the message content).

## 13. Collector contract (what Phase 3 must implement)

- Sources: `~/.claude/projects/*/<session-uuid>.jsonl`, resolved by explicit
  setting → `CLAUDE_CONFIG_DIR` → platform default `~/.claude`; data dir never
  hardcoded.
- Read pattern: read-only JSONL parsing (no snapshot needed — files are
  append-only immutable once written; an in-place partially-written line is
  tolerated by skipping unparseable lines with a warning).
- Collect: lines with `type == "assistant"`, `message.role == "assistant"`, and a
  present `message.usage`. Key: `{session_id}:{message.id}` — namespaced bare
  `message.id`, per Phase 1 §4's pinned convention, so a resumed session's copies
  stay distinct and cross-platform id collisions with Cline/OpenCode's ids cap.
- Fields per event: `message.model` → `model_id`, provider inference per §5.3 →
  `provider_id` (default `unknown`), `usage.input_tokens/output_tokens` → primary
  counts, `cache_read_input_tokens` → cache read, `cache_creation_input_tokens` →
  cache write, `output_tokens_details.thinking_tokens` → reasoning, `timestamp`
  → UTC, `usage_status` = `"reported"` when the usage object is present else
  `"unavailable"`.
- Dedup: `(session_id, message.id)`-distinct only; multiple lines of one
  `message.id` collapse to one record (first-seen timestamp, latest-seen usage —
  they are identical in practice).
- Never collect `cost-state` lines; `modelUsage` there is a mid-session snapshot,
  not an authoritative sum.
- Cross-check: per-model sums of `message.id`-distinct usage must be ≤ the final
  `cost-state` `modelUsage` for the same file (equal on the 3 sessions where the
  store was flushed after the final request).

*Clean-Code notes (ch08 Boundaries): the JSONL line shape plus `message.usage` are
third-party boundaries. Phase 3 must wrap them in a single adapter package (the
Claude Code collector) exposing only the normalized usage schema, with learning
tests pinning the line shapes documented above so a Claude Code upgrade that
changes them fails fast in tests, not silently in totals.*
