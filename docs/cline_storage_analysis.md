# Cline CLI Storage Analysis (Phase 1 Deliverable)

Verified against Cline CLI **3.0.70** on Linux, using the live local store
in `~/.cline/data`. All reads below were performed against file copies or
with read-only tools; the live store was never written to. Session-file
messages were parsed with Python `json.load`; `sessions.db` was queried via
a `/tmp` copy. Counts reflect the store as observed on 2026-10-11
(42 session dirs, 41 `sessions.db` rows, 2065 assistant messages).

Companion to `docs/opencode_storage_analysis.md`, which covers the OpenCode
side. Together they are the field maps Phase 2's collector must implement.

## 1. Verified storage locations

| Path | Purpose |
|---|---|
| `~/.cline/data/db/sessions.db` | **Session index.** SQLite table `sessions` (28 columns): one row per session with `session_id`, `provider`, `model`, `status`, `started_at`, `messages_path`, `metadata_json`. Confirmed by copying to `/tmp` and querying. |
| `~/.cline/data/sessions/<session_id>/<session_id>.messages.json` | **Authoritative usage.** Per-request records: `messages[].{id, role, ts, modelInfo, metrics}`. 42 files observed. |
| `~/.cline/data/sessions/<session_id>/<session_id>.json` | Session envelope: `provider`, `model`, `status`, `started_at`, `metadata.usage` / `metadata.aggregateUsage` (session totals — validation/cross-check only, never an ingestion source). |
| `~/.cline/data/settings/providers.json` | Provider registry (`version`, `lastUsedProvider`, `modes`, `providers`). Capability context only — never for keys; off-limits to the collector. |
| `~/.cline/data/settings/global-settings.json` | UI prefs. No usage. |
| `~/.cline/data/db/tasks.db` | Agenda tasks (`agenda_tasks`, `agenda_task_runs`). Scheduling domain — not usage-authoritative. |
| `~/.cline/data/db/hub-runs-hub-production.db` | `hub_runs`. Run orchestration — not usage-authoritative. |
| `~/.cline/data/logs/` | Telemetry/JSONL logs (~32M). Not a collection source. |
| `~/.cline/data/checkpoint-scratch/` | Git checkpoint snapshots. Not usage. |

Custom data directories: `cline --help` documents `--data-dir <path>`
(default `~/.cline/data`) and `--config <path>` (default `~/.cline`).
No `CLINE_*` env vars are set here and XDG vars are empty, so the defaults
above apply. The collector must resolve the data dir in the same order the
CLI does — explicit setting, then `--data-dir`/`--config` equivalent, then
platform default — and must never hardcode any platform path. Windows uses
`%LOCALAPPDATA%`-style layout and macOS follows the same `~/.cline` layout;
both are unverified here (Linux only), so runtime resolution plus a logged
fallback is required, mirroring the OpenCode locator.

Machine CLI surface (all verified live): `cline --version` → `3.0.70`;
`cline history --json --limit N` lists sessions newest-first with
`sessionId`, `status` (`idle` while running), `provider`, `model`,
`messagesPath`; `cline config --json` prints workspace rules/skills/MCP —
no data-dir pointer, so it is not a discovery source.

## 2. Supported storage formats

JSON files plus one SQLite index in the installed version.

`sessions.db` tables: `sessions`, `subagent_spawn_queue`, `schedules`,
`schedule_executions` (+ `sqlite_sequence`). Only `sessions` is
usage-relevant. Full column list (28):

```sql
session_id TEXT PRIMARY KEY, source, pid, started_at TEXT, ended_at TEXT,
exit_code INTEGER, status TEXT, status_lock INTEGER, interactive INTEGER,
provider TEXT NOT NULL, model TEXT NOT NULL, cwd, workspace_root, team_name,
enable_tools, enable_spawn, enable_teams INTEGER NOT NULL,
parent_session_id TEXT, parent_agent_id TEXT, agent_id TEXT,
conversation_id TEXT, is_subagent INTEGER NOT NULL DEFAULT 0,
prompt TEXT, metadata_json TEXT, transcript_path TEXT, hook_path TEXT,
messages_path TEXT, updated_at TEXT NOT NULL
```

Live counts: 41 rows; statuses `completed:29, failed:8, cancelled:4`;
`provider = cline` on all 41 rows; `is_subagent = 0` and
`parent_session_id IS NULL` on every row (subagent columns exist but are
unused in this store — the collector must still key defensively, see §9).

One orphan session dir exists (42 dirs vs 41 db rows); a reader that trusts
the db alone would miss it. Discovery must union the db index with a
directory scan of `data/sessions/`.

Each `.messages.json` top-level shape (all 42 files identical keys):

```json
{ "version": 1, "updated_at": "...", "agent": "lead",
  "sessionId": "<id>", "origin": "cli",
  "messages": [ ... ], "system_prompt": "..." }
```

`agent` is `"lead"` on every file observed; roles are exactly
`{user, assistant}` (2510 user / 2065 assistant); assistant content block
types are exactly `{text, thinking, tool_use, tool_result}`.

## 3. Relevant data structures

- Session envelope (`<id>.json`): one per conversation. `provider` /
  `model` = the session's *last* model, not per-request attribution.
  `metadata.usage` and `metadata.aggregateUsage` are identical session
  totals (verified equal on sampled sessions); `metadata` also carries
  `totalCost: 0`, `aggregatedAgentsCost: 0`, optional `terminal_marker*`
  (7/41 rows), `git`/`checkpoint` (35/41), and run config echo
  (`source/provider/model/enableTools/...`, 14/41).
- Assistant message (usage event): `{id, role:"assistant", content:[...],
  ts, modelInfo:{id, provider}, metrics:{...}}`. Stable primary key is the
  message `id` (`msg_*` normal, `error_*` for failed calls).
- User message: `{id, role:"user", content:[...], ts}` — never collected.
  `tool_result` blocks ride on user-role messages, so role alone cleanly
  separates billable calls from tool output.
- No reasoning/subagent token structures exist in this store version.

## 4. Token field definitions (authoritative source)

**Authoritative record = one assistant message, fields:**

```json
"modelInfo": { "id": "cline-free/gemini-3.8-flash", "provider": "cline" },
"metrics": { "inputTokens": 3989, "outputTokens": 113,
             "cacheReadTokens": 0, "cacheWriteTokens": 0 }
```

- 2038/2065 assistant messages carry a `metrics` object (98.7%); all 2038
  carry exactly the four keys above — no `total`, no `reasoning`, no
  variants. Field map: `inputTokens` → `input_tokens`,
  `outputTokens` → `output_tokens`, `cacheReadTokens` →
  `cache_read_tokens`, `cacheWriteTokens` → `cache_write_tokens`.
- There is no reported total. The collector computes
  `total = input + output` via the shared `calculate_totals` and must
  never treat `metadata.usage` as a per-request figure.
- `cacheWriteTokens` is 0 on every message observed (mirrors the OpenCode
  finding). Carry the field; a zero is stored as reported, not as unknown.
- Session totals equal the per-message sums — spot-checked exactly on two
  sessions (`1790495…`: 164635/10761/69019; `1790597…` with 302 msgs:
  28371041/45538/26575201). They are rollups for cross-check, redundant
  with messages. **Ingesting both double-counts every token.**
- `totalCost: 0` everywhere. Cost tracking is out of scope.

## 5. Model and provider identification

- Provider: `modelInfo.provider`. All 2065 assistant messages = `cline`.
  Third-party providers (OpenAI/Anthropic/OpenRouter/Ollama per plan §4.3)
  have zero rows locally — multi-provider *handling* is verified at the
  schema level (`modelInfo.provider` + `modelInfo.id` composite key), not
  with live rows. No provider allow-list: any `modelInfo.provider` is
  recorded uniformly.
- Model: `modelInfo.id`. Seven models observed:
  `stealth/space-bunny-alpha` (674),
  `cline-free/muse-spark-1.3-contributor` (582),
  `cline-free/step-5-preview` (317), `cline-free/gemini-3.8-flash` (217),
  `cline-free/mimo-v2.6-flash` (198), `cline-free/solar-mini4` (72),
  `cline-free/deepseek-v4.1-flash` (5).
- Tracker identity for a usage event: `(modelInfo.provider, modelInfo.id)`
  — matches the existing `breakdown_by_model` GROUP BY and the
  plan §3.3 independence rule.
- Model switching inside one session is confirmed live
  (`1790597…`: gemini + space-bunny; `1790704…`: space-bunny + mimo) —
  per-message attribution handles this; the session envelope's
  `provider`/`model` columns do not.

## 6. Timestamp interpretation

- `ts` is **integer milliseconds since Unix epoch, UTC** on all 2065
  assistant messages (zero missing, zero non-int). Range observed:
  2026-09-27 → 2026-10-11. Monotonic within each file checked.
- Usage timestamp for a usage event = message `ts`, normalized to aware
  UTC via the shared `normalize_timestamp`. Session `started_at` is
  fallback only when a message `ts` is absent.
- Checkpoint: `ts` plays the same role as OpenCode `time_created` — a
  stable resume point. Same-ms re-reads are safe under the existing
  `Checkpoint.covers()` `<` semantics plus the `(platform,
  source_event_id)` upsert.

## 7. Individual events vs cumulative counters

- Each assistant message **with `metrics`** is one usage event (one model
  call). Session `metadata.usage` equals the per-message sums, so messages
  are additive parts, not overlapping windows.
- `metadata.usage` / `metadata.aggregateUsage` are cumulative rollups over
  the session's messages. Cross-check only, never an additional source.
- No `part`-level token snapshots exist in this format — there is no
  OpenCode-style part/token double-count trap to avoid.

## 8. Streaming usage updates

- Unlike OpenCode (row at generation start, tokens backfilled), Cline
  messages arrive complete: the live `history --json` shows an `idle`
  session whose `.messages.json` already carries full `metrics` on every
  assistant message (63 msgs in the current session, all attributed).
  No in-flight marker field was found in the message schema.
- Collector rule: collect every assistant message carrying a `metrics`
  object. Messages without one are classified in §12, not treated as
  in-flight. The `ScanOutcome.pending_timestamps_ms` mechanism is still
  reused — a message file that grows between scans is picked up by the
  timestamp checkpoint, and the checkpoint hold-back logic needs no
  Cline-specific change.
- Retried/failed calls surface as separate `error_*` display messages
  (§12), not as mutated rows — there is no backfill window to guard.

## 9. Session compaction, retries, subagents

- Resumed/forked sessions DUPLICATE message rows: 108 `msg_*` ids appear
  in both `17914817…_rk99b` (failed) and `17914879…_lkq13` (completed)
  with identical `ts` and identical metrics — the later session is a copy
  of the earlier one's history. Bare `message.id` is therefore **not** a
  safe dedup key: keying on it alone under-counts the resume, while
  keying per-session double-counts the copied prefix.
- Within one session, ids are unique (0 within-session dups) — the hazard
  is only cross-session copies.
- Deduplication rule for Phase 2/3: `source_event_id` must namespace the
  message id (e.g. `{session_id}:{message_id}`), keeping the existing
  `(platform, source_event_id)` unique constraint effective. The resumed
  pair then stores both copies; a future resume-aware rule can supersede
  the failed session's rows, but correctness (no silent merge of distinct
  rows, no cross-platform collision with OpenCode's `msg_*` ids) comes
  first. This is the single largest accuracy decision in the integration.
- `error_*` ids (24) are unique per failure and safe under the same rule.
- Subagents: `is_subagent = 0` and no `parent_session_id` on all 41 rows;
  `agent: "lead"` on all 42 message files. No subagent rows exist to
  account for — the collector must still attribute by message-level
  `modelInfo` (not session level) so subagent usage, when it appears,
  lands on the right model without a schema change.
- History preservation: rows keyed by the namespaced id that vanish from
  source stay in the tracker DB; re-appearing ids upsert rather than
  duplicate — same contract as OpenCode.

## 10. Free-model token availability

Verified YES: 98.7% of assistant messages report full metric objects,
including all free-tier models (`cline-free/*` = 1174/2065 assistant
messages carry metrics). Token tracking does not depend on free vs paid.
The remaining 1.3% are classified in §12 — none are free-model gaps.

## 11. Third-party provider token availability

No third-party-provider messages exist locally (all = `cline` provider),
so per-provider completeness is unverifiable from live rows. Schema
finding: provider identity is always explicit (`modelInfo.provider` on
every assistant message, zero missing), so the collector treats any
provider uniformly and records `usage_status = "reported"` whenever a
`metrics` object is present, `"unavailable"` when absent — no provider
allow-list. Cline-owned, OpenAI, Anthropic, Google, OpenRouter,
OpenAI-compatible, Ollama/local (plan §4.3) all flow through the same
four-field map; a provider that reports fewer fields yields `None`
categories, never zeros.

## 12. Incomplete / interrupted requests

Observed representations (all preserved as rows):

| Case | Count | Representation |
|---|---|---|
| `error_*` display message, no `metrics` | 24 | Failed call (429 cap, 404 model, timeout, ECONNRESET). `metadata: {displayOnly: true, displayRole: "error"}`. → `usage_status = "unavailable"`, all counts NULL. |
| Thinking-only message, no `metrics` | 3 | Content is a single `thinking` block (e.g. `msg_K7JBt9wO`). No usage reported — not a billed call. → `unavailable`, never zero. |
| Zero-token with `metrics` present | 1+ | All-zero metric objects occur. → stored zeros with `usage_status = "reported"` (a reported zero is data, not absence). |

Rule: missing `metrics` object → `"unavailable"` (NULLs, contributes 0 to
sums, counted in `unknown_total_events`). Present object → `"reported"`,
even when all zeros. `cancelled`/`failed` session status does not change
per-message handling: billed calls inside them keep their metrics.

## 13. Known compatibility limitations

1. `cline history` output contains session envelopes only — no per-message
   ids, no metrics, no `ts`. Discovery aid / cross-check target, not a
   collection source.
2. `cline config --json` prints workspace config (rules/skills/MCP), not
   usage and not the data-dir pointer. Not a discovery source.
3. The live `sessions.db` is WAL-active while Cline runs; the collector
   must copy-then-read (or immutable URI) and must never open the live
   file read-write — same contract as the OpenCode snapshot module.
4. Message `id` values are stable within a session but NOT unique across
   sessions (108 cross-session dups observed) and NOT unique across
   platforms (OpenCode uses `msg_*` too). The namespaced
   `{session_id}:{message_id}` event id in §9 is mandatory, not optional.
5. Session totals (`metadata.usage`) duplicate message sums exactly —
   ingesting both doubles every figure. Request-level only.
6. Provider diversity is schema-ready but live-unverified (all rows
   `provider = cline`). First non-`cline` row should trigger a re-check of
   §4's four-field map before assuming it reports identically.
7. No `reasoning` tokens exist in this schema version. If a future Cline
   version adds a reasoning field, it needs its own overlap entry
   (`CLINE_RELATIONSHIPS`) with the same additive-vs-subset proof
   OpenCode's `categories.py` documents — never assume.
8. Version drift: CLI 3.0.70 vs `sessionHistoryOrigin` 3.0.65 in stored
   sessions. Learning tests must pin the §2–§4 shapes so a Cline upgrade
   that changes them fails fast in tests, not silently in totals.

## 14. Sanitized example records

Session envelope (usage rollup — cross-check only):

```json
{ "session_id": "1790495257388_6orlt", "provider": "cline",
  "model": "cline-free/gemini-3.8-flash", "status": "completed",
  "started_at": "2026-09-27T07:48:31.705Z",
  "metadata": { "usage": { "inputTokens": 164635, "outputTokens": 10761,
    "cacheReadTokens": 69019, "cacheWriteTokens": 0, "totalCost": 0 } } }
```

Assistant message (usage event — the collected record):

```json
{ "id": "msg_3belytgo", "role": "assistant", "ts": 1790495317187,
  "modelInfo": { "id": "cline-free/gemini-3.8-flash", "provider": "cline" },
  "metrics": { "inputTokens": 3989, "outputTokens": 113,
               "cacheReadTokens": 0, "cacheWriteTokens": 0 } }
```

Error message (incomplete — `unavailable`, never zero):

```json
{ "id": "error_8f2910ca-c1ba-4f34-aee0-ac76cbd441ce", "role": "assistant",
  "ts": 1790600459064,
  "modelInfo": { "id": "cline-free/gemini-3.8-flash", "provider": "cline" },
  "metadata": { "displayOnly": true, "displayRole": "error" },
  "content": [{ "type": "text",
    "text": "{\"error\":{\"code\":\"INFERENCE_CAP_ERROR\"}}" }] }
```

## 15. Collector contract (what Phase 2 must implement)

- Source: `sessions.db` table `sessions` (index: `session_id`,
  `messages_path`, `metadata_json`) unioned with a directory scan of
  `data/sessions/` (orphan-dir tolerant), resolved via explicit setting →
  `--data-dir`/`--config` equivalent → platform default.
- Read pattern: copy-then-read the db; read-only JSON parses; never write
  to `~/.cline`, never read or store keys (`providers.json` is off-limits
  to the collector).
- Collect: every `role == "assistant"` message carrying a `metrics`
  object. Key: `{session_id}:{message_id}` namespaced event id.
  Fields per message: `modelInfo.provider` → `provider_id`,
  `modelInfo.id` → `model_id`, `metrics.inputTokens/outputTokens` →
  `input/output`, `metrics.cacheReadTokens/cacheWriteTokens` → cache
  categories (additive: `CLINE_RELATIONSHIPS`), `ts` → UTC timestamp,
  missing `metrics` → `unavailable` row (NULLs, never zero).
- Never ingest `metadata.usage`/`aggregateUsage` as usage — session totals
  are validation-only.
- Never sum across files by bare `message.id` — the 108 resume-duplicate
  ids prove it double-counts or merges.
- Cross-check: per-model sums should reconcile with session-envelope
  `metadata.usage` totals; per-message sums equal them exactly on the
  sessions checked.

*Clean-Code notes (ch08 Boundaries): the `sessions.db` schema plus the
`.messages.json` shape are third-party boundaries — Phase 2 must wrap them
in a single adapter package (the Cline collector) exposing only the
normalized usage schema, with learning tests pinning the SQL/JSON shapes
documented above so a Cline upgrade that changes them fails fast in tests,
not silently in totals.*
