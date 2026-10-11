# Codex CLI Storage Analysis (Phase 5 Deliverable)

Verified against **codex-cli 0.155.1** on Linux (`~/.local/bin/codex`), using the live
local store. All reads were performed directly against the JSONL rollouts and the
SQLite index; nothing was written back and no prompt, response, tool-argument, or
source text was extracted — only field names, integer token counts, and identifiers.
Counts reflect the store as observed on 2026-10-12: **5 rollout files, 2,024 lines,
229 `token_usage_record` events, 19 turns.**

Companion to `docs/claude_storage_analysis.md`, `docs/cline_storage_analysis.md`, and
`docs/opencode_storage_analysis.md`. This is the field map the **Phase 6** collector
must implement.

> **Headline finding:** unlike the plan's guess, the authoritative usage source is a
> dedicated top-level **`token_usage_record`** event whose per-call `usage` object
> reconciles *exactly* against both the in-file cumulative counter and the SQLite
> index (3 independent sources agree on all 5 threads). The plan's candidate
> `token_count` / `last_token_usage` / `total_token_usage` also exist but live inside
> `event_msg` and are a redundant mirror that **double-emits on an aborted turn** —
> summing them overcounts by 296,634 tokens on the largest thread.

## 1. Verified storage locations

Codex resolves a **`CODEX_HOME`** root (default `~/.codex`, overridable). On this
machine the active home is **`~/Desktop/Projects/codex`** (the default `~/.codex` also
exists but holds an *empty* `threads` index and no rollouts — it is not the live store).
The locator must resolve: `CODEX_HOME` env → platform default `~/.codex`, logging any
fallback; never hardcode.

| Path (relative to `CODEX_HOME`) | Purpose |
|---|---|
| `sessions/YYYY/MM/DD/rollout-<ISO-ts>-<session-uuid>.jsonl` | **Authoritative usage.** One JSONL file per session (thread), partitioned by date. |
| `state_5.sqlite` → `threads` | Session index: `id`, `rollout_path`, `model_provider`, `model`, `tokens_used`, `archived`, timestamps. Cross-check / discovery aid (§7). |
| `session_index.jsonl` | Lightweight index (`id`, `thread_name`, `updated_at`). Discovery aid only — no tokens. |
| `history.jsonl` | Prompt history (`session_id`, `text`, `ts`). **Prompts — never read.** |
| `config.toml` | Provider/model config. Read for non-secret provider *names* only (§5.3). |
| `thread_history_1.sqlite` (`thread_turns`, `thread_items`) | Normalized projection of turns/items; not a usage source. |
| `archived_sessions/` | **Does not exist** on this machine (§8). |
| `logs_2.sqlite`, `goals_1.sqlite`, `memories_1.sqlite`, `queue_1.sqlite` | Not usage sources. |

`threads.rollout_path` points into `sessions/…` for all 5 rows, confirming rollouts
never move on archive (§8).

## 2. Supported storage formats

JSONL only. Every line shares one envelope:

```json
{ "timestamp": "2026-09-22T12:53:40.376Z", "ordinal": 0,
  "type": "session_meta", "payload": { … }, "metadata": { … } }
```

Top-level `type` counts across all 5 files (2,024 lines):

```
response_item:897  event_msg:862  token_usage_record:229
turn_context:19    world_state:12 session_meta:5
```

`event_msg` `payload.type` distribution:

```
item_completed:577  token_count:230  task_started:19
thread_settings_applied:17  task_complete:16  turn_aborted:3
```

`response_item` `payload.type` distribution (content — **never collected**):

```
message:188  reasoning:155  function_call:202  function_call_output:202
custom_tool_call:75  custom_tool_call_output:75
```

Only `type == "token_usage_record"` lines carry usage (§3). `event_msg` with
`payload.type == "token_count"` carries a redundant mirror (§4.2).

**Version drift / plan-field mapping.** Installed 0.155.1 (`version.json` reports
latest 0.157.0). Every candidate the plan predicted is present, though some are nested
rather than top-level:

| Plan candidate | Present? | Location |
|---|---|---|
| `event_msg` | ✅ | top-level `type` |
| `token_count` | ✅ | `event_msg.payload.type` |
| `last_token_usage` | ✅ | `event_msg.payload.info.last_token_usage` |
| `total_token_usage` | ✅ | `event_msg.payload.info.total_token_usage` |
| `turn_context` | ✅ | top-level `type` |
| model metadata | ✅ | `turn_context.payload.model`, `session_meta.payload.model_provider` |
| session timestamps | ✅ | line `timestamp`, `session_meta.payload.timestamp` |
| *(not predicted)* | ⚠️ | **`token_usage_record`** — top-level; the authoritative source |

## 3. Relevant data structures

**`token_usage_record` line (the usage event):**

```json
{ "timestamp": "…", "ordinal": 12, "type": "token_usage_record",
  "payload": {
    "thread_id": "01a0c92d-d997-7c82-8c58-5a5312cc8008",
    "session_id": "01a0c92d-d997-7c82-8c58-5a5312cc8008",
    "turn_id":    "01a0c92d-f015-7da1-9752-b688d532e5e7",
    "root_turn_id": "01a0c92d-f015-7da1-9752-b688d532e5e7",
    "response_id": "f2f7a3a0-8b6f-47de-bec8-b4b574e63f12",
    "usage":            { "input_tokens": 9798, "cached_input_tokens": 3456,
                          "cache_write_input_tokens": 0, "output_tokens": 11,
                          "reasoning_output_tokens": 0, "total_tokens": 9809 },
    "turn_token_usage": { …same 6 fields… },
    "thread_token_usage": { …same 6 fields… }
  } }
```

Three usage scopes ride on every record — the core of §4:

- **`usage`** — this single API call (incremental). ✅ authoritative.
- **`turn_token_usage`** — running total for the current turn; **resets** at each new `turn_id`.
- **`thread_token_usage`** — running total for the whole thread; **monotonic**, never resets.

**`event_msg` / `token_count` (redundant mirror):**

```json
{ "type": "event_msg",
  "payload": { "type": "token_count",
    "info": { "total_token_usage": { …6 fields… },
              "last_token_usage":  { …6 fields… },
              "model_context_window": 258400 },
    "rate_limits": { … } } }
```

`last_token_usage` == per-call (`usage`); `total_token_usage` == thread-cumulative.

**`turn_context` line (model context):** payload keys → `turn_id`, `root_turn_id`,
`cwd`, `workspace_roots`, `current_date`, `timezone`, `approval_policy`,
`sandbox_policy`, **`model`**, `personality`, `collaboration_mode`, `summary`,
`comp_hash`, **`effort`**, … One per turn (19/19). Join to a usage record on `turn_id`.

**`session_meta` line (first line of each file):** payload keys → **`session_id`**,
`id`, `timestamp`, `cwd`, `runtime_workspace_roots`, `originator`, **`cli_version`**,
`source`, `thread_source`, **`model_provider`**, `base_instructions`, `history_mode`,
`context_window`.

## 4. Token field definitions (authoritative source)

**Authoritative record = one `token_usage_record`, fields from its `usage` object:**

| Source field | Meaning | Evidence (n=229) |
|---|---|---|
| `input_tokens` | Prompt tokens (incl. cached) | present 229/229 |
| `output_tokens` | Completion tokens (incl. reasoning) | present 229/229 |
| `cached_input_tokens` | Prompt tokens served from cache | non-zero 228/229 |
| `cache_write_input_tokens` | Prompt tokens written to cache | 0/229 (always 0 here) |
| `reasoning_output_tokens` | Reasoning tokens inside output | non-zero 155/229 |
| `total_tokens` | Reported total | `== input + output` 229/229 |

Field map: `input_tokens` → `input_tokens`, `output_tokens` → `output_tokens`,
`cached_input_tokens` → `cache_read_tokens`, `cache_write_input_tokens` →
`cache_write_tokens`, `reasoning_output_tokens` → `reasoning_tokens`,
`total_tokens` → `total_tokens` (reported; equals `calculate_totals`'s `input+output`).

### 4.1 Overlap semantics → `CODEX_RELATIONSHIPS` (Phase 6 / registration input)

Arithmetic invariants verified on all 229 records:

- `total_tokens == input_tokens + output_tokens` — **229/229**
- `cached_input_tokens <= input_tokens` — **229/229** → cache is a **subset of input**
- `reasoning_output_tokens <= output_tokens` — **229/229** → reasoning is a **subset of output**

So unlike OpenCode (additive), Codex reports cache and reasoning *inside* input/output —
the OpenAI-style layout. This is exactly what the reuse audit deferred to Phase 5:

```python
CODEX_RELATIONSHIPS = CategoryRelationships(
    cache_overlap="subset_of_input",
    reasoning_overlap="subset_of_output",
)
```

`consumption_tokens` therefore must **not** re-add cache/reasoning; shared
`calculate_totals` already honors `subset_of_*` (proven by `CLAUDE_RELATIONSHIPS`).

### 4.2 Cumulative vs per-turn vs per-call (Critical Accounting Rule)

**Do not add cumulative totals to per-turn usage.** Verified reconciliation per file:

| Rollout (MM-DD) | lines | `token_usage_record` | `sum(usage.total)` | final `thread_token_usage.total` | `threads.tokens_used` | match |
|---|---|---|---|---|---|---|
| 09-22 18:23 | 13 | 1 | 9,809 | 9,809 | 9,809 | ✅ |
| 09-22 18:36 | 17 | 1 | 6,882 | 6,882 | 6,882 | ✅ |
| 09-25 09:51 | 203 | 20 | 806,420 | 806,420 | 806,420 | ✅ |
| 09-25 17:35 | 1,581 | 181 | 31,769,703 | 31,769,703 | 31,769,703 | ✅ |
| 09-25 22:53 | 210 | 26 | 739,546 | 739,546 | 739,546 | ✅ |

Three independent sources agree on every thread: **(a)** summing per-call `usage`,
**(b)** the final in-file `thread_token_usage`, **(c)** the SQLite `threads.tokens_used`.

**Rule for Phase 6:** treat per-call `usage` as the authoritative increment and store one
row per `token_usage_record`. Use `thread_token_usage` / `threads.tokens_used` **only as a
reconciliation check** — never as rows to insert. `turn_token_usage` resets each turn
(observed 10 resets across 11 turns on the 17:35 thread) and is per-turn context only.

**Why not sum `token_count`?** The two sources are interleaved `T c T c …` and
`info.last_token_usage == usage` positionally on **every** pair (1,1,20,181,26). But
`token_count` fires **230** times vs **229** `token_usage_record`: on the 17:35 thread an
**aborted final turn emitted an extra `token_count` with no matching
`token_usage_record`**, so `sum(token_count.last) = 32,066,337` vs the true
`31,769,703` — an overcount of **296,634** (the last call double-emitted). Prefer
`token_usage_record`, which reconciles exactly.

## 5. Model and provider identification

### 5.1 Model

- `turn_context.payload.model` is a plain string, one per turn. This store:
  `"deepseek-flash"` (19/19 turns). `effort` / `collaboration_mode.settings.model`
  corroborate.
- A usage record's model = the `turn_context` with the **same `turn_id`** (exact join).
- If no `turn_context` precedes a record, preserve the usage with `model_id="unknown"`.
- **Model switching:** only **1 distinct model** across all 5 sessions → no local
  switching evidence. Per-turn `model` handles switching without a schema change (same
  posture as the other platforms).

### 5.2 Third-party routing (validated live)

`session_meta.payload.model_provider == "deepseek"` (5/5) and the model string
`deepseek-flash` prove a non-OpenAI provider drives Codex CLI here. Attribution splits
into two axes: `model_id` = the model string; `provider_id` = the provider (§5.3).

### 5.3 Provider

First-class provider identifiers exist (unlike Claude Code), in priority order:

1. **`session_meta.payload.model_provider`** — authoritative per session (`deepseek`).
   Mirrored by `state_5.sqlite → threads.model_provider`.
2. **`config.toml`** — top-level `model_provider` and `[model_providers.<id>]` blocks
   with `name`, `base_url`, `wire_api`, and **`env_key`** (an env-var *name*, e.g.
   `DEEPSEEK_API_KEY`). Read **names only**; **never** read any env-var *value* or
   credential (plan §12).
3. Model-string prefixes for known gateways when an explicit provider is absent
   (`openrouter/…`, `bedrock/…`, `deepseek/…`, `glm/…`, `kimi/…`, `gpt-…`), applied to the
   model string only.
4. Everything else → `"unknown"`, honestly represented, never guessed (plan §4.3).

## 6. Timestamps

Every line carries `timestamp` — ISO-8601 UTC with milliseconds
(`2026-09-22T12:53:40.376Z`), stable across re-reads. `session_meta.payload.timestamp`
anchors session start; `event_msg.item_completed` also carries `started_at_ms` /
`completed_at_ms`. Observed range 2026-09-22 → 2026-09-25. Normalize with the shared
`normalize_timestamp`; the line `timestamp` is the usage event's timestamp.

## 7. Identifiers and deduplication

| Identifier | Scope | Use |
|---|---|---|
| `session_id` == `thread_id` | one session | == UUID in filename (`rollout-<ts>-<uuid>.jsonl`); globally stable |
| `response_id` | one API call | unique per call (0 duplicates across all files) |
| `turn_id` | one turn | groups calls in a turn; joins to `turn_context.model` |
| `ordinal` | line order | monotonic position within the file |
| `timestamp` | line time | event time |

**Dedup key (Cline `namespaced_event_id` convention):** `source_event_id =
"{session_id}:{response_id}"`. One row per API call; idempotent upsert on the shared
unique `(platform, source_event_id)`. No repeated-record inflation was found: every
`response_id` appears exactly once (unlike Claude Code's multi-line-per-request pattern).

## 8. Active vs archived sessions (duplicate handling)

- **Archival is a database flag, not a file move.** `threads.archived` is `INTEGER`
  (0=active, 1=archived); `archived_at` holds the time. Files remain under `sessions/…`
  regardless (`threads.rollout_path` still points there).
- **No `archived_sessions/` directory exists** anywhere under home (the plan's candidate
  location is absent in 0.155.1). If a future version introduces one, identity stays the
  session UUID, so the same session read from either location upserts once.
- This store: 5 threads, **0 archived**, and **each session appears in exactly one
  location** (filename-UUID scan found no rollout duplicated across directories).
- Discovery must therefore be driven by `sessions/**/rollout-*.jsonl` (and optionally the
  `threads` index), keyed on the session UUID — active and archived alike — so a session
  is never counted twice.

## 9. Retry, abort, and compaction

- **Aborted turns:** `event_msg / turn_aborted` (3, `reason="interrupted"`). An abort can
  emit an extra `token_count` without a `token_usage_record` (§4.2) — another reason to
  key on `token_usage_record`, not `token_count`.
- **Retries:** no retry duplicates observed (`response_id` all unique). A retried call
  would be a new `response_id`/`token_usage_record` and is legitimately counted once.
- **Compaction:** no dedicated compaction event. `turn_context` carries `summary`,
  `comp_hash`, and `history_mode: "paginated"` — context is paginated/compacted between
  turns, but `thread_token_usage` stays **monotonic across all 11 turns**, so compaction
  never resets accounting. Use per-call `usage` and compaction/retries cannot inflate
  totals.

## 10. Cross-version compatibility

0.155.1 rollouts use the envelope + `token_usage_record` shape documented above. The
learning tests must pin: the 6 top-level line types, the `token_usage_record` keyset
(`thread_id`, `turn_id`, `session_id`, `root_turn_id`, `response_id`, `usage`,
`turn_token_usage`, `thread_token_usage`), the 6-field usage object, and the
`{timestamp, ordinal, type, payload}` envelope — so an upgrade that renames fields (or
moves usage) fails in tests, not silently in totals. Note the plan's field guesses are
already out of date relative to 0.155.1 (§2); pin against observed reality.

## 11. Privacy

- Only `token_usage_record` lines are decoded; `response_item` content
  (`message`/`reasoning`/tool calls) and `base_instructions` are **never** extracted.
- `history.jsonl` (prompt text) is never read.
- `config.toml` is read for non-secret provider *names* and `env_key` (an env-var name)
  only — **values and credentials are never read** (plan §12).
- The tracker DB stores only §4's mapped fields + identifiers + the raw `usage` JSON
  (not message content).

## 12. Collector contract (what Phase 6 must implement)

- Sources: `$CODEX_HOME/sessions/**/rollout-*.jsonl`, resolved `CODEX_HOME` env →
  `~/.codex`; never hardcoded. Discover files (optionally cross-check with
  `threads.rollout_path`); skip unparseable lines with a warning (append-only files).
- Collect: lines with `type == "token_usage_record"` and a present `usage`.
- **Key:** `source_event_id = "{session_id}:{response_id}"` (Cline convention).
- **Authoritative usage = `usage` (per-call).** Never insert `turn_token_usage` or
  `thread_token_usage` rows; use them only to reconcile (§4.2).
- Fields per event: `model_id` = `turn_context.model` joined on `turn_id` (else
  `"unknown"`); `provider_id` = `session_meta.model_provider` per §5.3 (else `"unknown"`);
  `session_id`/`thread_id` → `session_id`; token map per §4; `timestamp` → UTC;
  `usage_status = "reported"` when `usage` present else `"unavailable"`.
- Register `CODEX_RELATIONSHIPS = CategoryRelationships(cache_overlap="subset_of_input",
  reasoning_overlap="subset_of_output")` (§4.1).
- Dedup: one row per `source_event_id`; active and archived sessions share the session
  UUID so a session is never counted twice (§8).
- Cross-check: per-thread `sum(usage.total)` must equal final `thread_token_usage.total`
  (and `threads.tokens_used`) — assert this in a reconciliation test.

*Clean-Code notes (ch08 Boundaries): the JSONL envelope + `token_usage_record.payload`
are third-party boundaries. Phase 6 must wrap them in a single adapter package (the Codex
collector) exposing only the normalized usage schema, with learning tests pinning the
shapes above so a Codex upgrade that changes them fails fast in tests, not silently in
totals.*



