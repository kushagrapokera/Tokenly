# OpenCode Storage Analysis (Phase 1 Deliverable)

Verified against OpenCode **1.18.35** on Linux using the live local database.
All queries below were run read-only against an immutable file copy
(`sqlite3 "file:...?immutable=1"`), never against the live DB.

## 1. Verified storage locations

| Path | Purpose |
|---|---|
| `~/.local/share/opencode/opencode.db` | **Authoritative store.** SQLite, WAL mode (`opencode.db-wal`, `opencode.db-shm`). Confirmed via `opencode db path` and `opencode debug paths` (`data = ~/.local/share/opencode`). |
| `~/.local/share/opencode/storage/session_diff/` | Session diff snapshots (1 JSON file observed). Not usage-authoritative. |
| `~/.local/share/opencode/storage/migration` | Migration marker. Not usage-authoritative. |
| `~/.local/share/opencode/log/opencode.log` | Runtime log. Not usage-authoritative. |
| `~/.config/opencode/opencode.jsonc` | User config (MCP servers etc.). Contains no paths, no usage. |
| `~/.cache/opencode`, `~/.local/state/opencode`, `/tmp/opencode` | Cache/state/tmp from `opencode debug paths`. No usage records. |

Custom data directories: no `OPENCODE_*` env var is set in this environment and
`opencode.jsonc` defines no data-directory key, so the default above applies.
If a custom directory is ever configured, re-run `opencode debug paths` —
the `data` line is the source of truth, and the collector must resolve it the
same way (shell out to `opencode debug paths`) rather than hardcoding `~`.

Platform coverage: Linux paths above are verified live on this machine.
macOS follows the same XDG layout (`~/.local/share/opencode`) per upstream
docs; Windows uses `%LOCALAPPDATA%\opencode` — both are **unverified here**
(no macOS/Windows machine available). The collector therefore must never
hardcode any platform path: resolve at runtime by shelling out to
`opencode db path` (prints the full DB path directly) or
`opencode debug paths`, which are platform-independent and also honor custom
data directories. Discovery is OS-agnostic by construction; only the
verified-Linux fallback default (`~/.local/share/opencode/opencode.db`) may
be consulted if the shell-out fails, and that failure must be logged.

## 2. Supported storage formats

SQLite only in the installed version. 19 tables observed:

`workspace, data_migration, account_state, account, control_account,
credential, event_sequence, event, permission, project_directory, project,
message, part, session_context_epoch, session_input, session_message,
session, todo, session_share, migration`

Live counts: 26 sessions, 1731 messages (143 user / 1588 assistant),
6060 parts, 21751 events, 3 projects. `session_message` and `session_input`
are empty (legacy/unused in this version) — the collector must ignore them.

`message.data` and `part.data` are JSON blobs; all usage fields live inside
them, not in SQL columns (except the `session` rollups, see §4).

## 3. Relevant data structures

- `session` row: one per conversation. Columns include `cost`,
  `tokens_input/output/reasoning/cache_read/cache_write`, `model` (JSON
  `{"id","providerID","variant?"}` = *last* model used), `time_created`,
  `time_updated`, `time_compacting`, `parent_id`.
- `message` row: one per user or assistant turn. `data.role` is `user` or
  `assistant`. Stable primary key `message.id` (`msg_*`).
- `part` rows: sub-steps of a message (`text`, `reasoning`, `tool`,
  `step-start`, `step-finish`, `patch`). `step-finish` carries a `tokens`
  snapshot but it is **cumulative within the message**, not per-step —
  see §6. Parts carry no usage value for the tracker beyond this caveat.
- `event` rows: `message.part.updated.1`, `message.updated.1`,
  `session.updated.1`, `session.created.1`, `message.removed.1`.
  Streaming updates arrive as events, then settle into `message.data`.

## 4. Token field definitions (authoritative source)

**Authoritative record = one assistant `message` row, fields:**

```json
"tokens": {
  "total": 8297, "input": 6478, "output": 27, "reasoning": 0,
  "cache": { "read": 1792, "write": 0 }
},
"cost": 0, "finish": "stop",
"time": { "created": 1789532819792, "completed": 1789532824807 }
```

- Every assistant message (1588/1588) carries a `tokens` object — none missing.
- `tokens.total` is present on most messages but missing on 335/1588, so the
  collector must compute `total = input + output` and never rely on `total`.
- `total ≈ input + output + reasoning + cache.read` is **not** exact
  (e.g. total=8297 vs 6478+27+0+1792=8297 here, but other rows diverge),
  so `input`/`output` are the MVP fields; `reasoning`/`cache.*` are
  overlapping sub-categories that must never be added into the total.
- `session.tokens_*` columns exactly equal `SUM(message.tokens_*)` (verified
  on 3/3 sampled sessions) — they are rollups, redundant with messages.
- `cost` is 0 on all 1731 messages and all 26 sessions (free-tier usage).
  Cost tracking is out of scope; the field exists for future paid usage.

## 5. Model and provider identification

Assistant message keys (all four keysets observed):

`role, parentID, mode, agent, path, cost, tokens, modelID, providerID,
 time, finish` (+ optional `variant`, optional `error`)

- Provider: `data.providerID`. All 1588 assistant messages = `opencode`.
  Third-party providers (deepseek etc. appear in `opencode models` output)
  have zero messages locally — multi-provider *handling* is verified at the
  schema level (`providerID` + `modelID` composite key), not with live rows.
- Model: `data.modelID` (+ optional `data.variant`: `xhigh` on 1181 msgs,
  `max` on 1, absent on 406). Models seen: `space-bunny-free` (716),
  `muse-spark-1.3-contributor-free` (465), `union-alpha` (405),
  `big-pickle` (1), `fledge-alpha-free` (1).
- Tracker identity for a usage event: `(providerID, modelID)` — variant is
  metadata, not identity (same model billed/tracked together).
- 3/26 sessions contain multiple models (verified sets, e.g.
  `{space-bunny-free, muse-spark-1.3}` in one session) — per-message
  attribution handles this; session-level `model` column does not.

## 6. Timestamp interpretation

- All times are **integer milliseconds since Unix epoch, UTC**
  (e.g. `1789532819759` = `2026-09-16T04:26:59.759Z`). Verified by
  converting oldest and newest `message.time_created` values.
- Usage timestamp for a usage event = assistant message
  `data.time.created`. `data.time.completed` is present on all 1588
  assistant messages (0 missing) and marks generation end; use it only
  for duration diagnostics, never for calendar bucketing.
- Range observed: 2026-09-16 → 2026-10-08 (23 days per `opencode stats`).

## 7. Individual events vs cumulative counters

- Each assistant `message` row is **one usage event** (one model call),
  even when several share the same `parentID` (normal multi-turn flow:
  one user message → N assistant messages, each a separate billed call).
- `part.step-finish.tokens` snapshots are cumulative *within* their parent
  message — summing them double-counts. The collector must read tokens
  only from `message.data.tokens`, never from parts.
- `session.tokens_*` are cumulative rollups over the session's messages
  (verified equal to the message sums). Useful as a cross-check, never as
  an additional source to sum.

## 8. Streaming usage updates

- Live generation streams through `event` rows
  (`message.part.updated.1` x13171, `message.updated.1` x6637 observed);
  the `message.data.tokens` object is written when the call completes.
- Collector rule: only collect messages whose `data.time` contains
  `completed`. All 1588 local assistant messages qualify. A message without
  `completed` is in-flight and must be picked up on the next incremental
  scan, keyed by stable `message.id` (upsert, not append).

## 9. Session compaction and retry behavior

- Compaction: `session.time_compacting` is NULL on all 26 sessions — no
  compaction has occurred locally. When it does, message rows may be
  summarized but already-collected usage events (keyed by `message.id`)
  remain valid in the tracker's DB; the collector must never delete on
  seeing compaction.
- Retries: `message.removed.1` events exist (9 observed) — a retried call
  leaves its original message row removed. Collector rule: rows keyed by
  `message.id` that vanish from source stay in the tracker DB (history
  preservation), and re-appearing ids upsert rather than duplicate.
- `parentID` is **not** a dedup key: multiple assistant messages routinely
  share one `parentID` (up to 192 in one session) as sequential tool-call
  steps. Dedup key is `message.id` alone.

## 10. Free-model token availability

Verified YES: 100% of assistant messages report full token objects,
including all free-tier models (`*-free` models = 1182/1588 messages,
`union-alpha`/`big-pickle` = 406/1588). `opencode stats` independently
confirms: Input 8.8M, Output 446.8K, Cache Read 110.9M across 26 sessions.
Token tracking does not depend on free vs paid.

## 11. Third-party provider token availability

No third-party-provider messages exist locally (all 1588 = `opencode`
provider), so per-provider completeness is unverifiable from live rows.
Schema finding: provider identity is always explicit (`providerID` on every
assistant message), so the collector treats any `providerID` uniformly and
records `usage_status = "reported"` whenever a `tokens` object is present,
`"unavailable"` when absent — no provider allow-list.

## 12. Incomplete / interrupted requests

Observed representations (all preserved as rows, all collectible):

| Case | Count | Representation |
|---|---|---|
| `finish = "unknown"` | 321 | Completed call, provider gave no finish reason. Tokens present — count normally. |
| `finish` key absent | 14 | Same as above, older schema shape. Tokens present — count normally. |
| `error` present (`MessageAbortedError`) | 14 | Interrupted call. `tokens` = all zeros — records as zero-token event, never as missing. |
| Zero-token non-error | 1+ | e.g. `union-alpha` row with all-zero tokens, no error. Record zeros with `usage_status = "reported"`. |

Rule: missing `tokens` object → `usage_status = "unavailable"`, all counts
NULL (not zero). Present object → `"reported"`, even when all zeros.


## 13. Known compatibility limitations

1. `opencode stats` CLI output (Overview / Cost and Tokens / Model Usage /
   Tool Usage) contains only aggregates — no per-message ids, no
   timestamps, no error/finish detail. It is a cross-check target, not a
   collection source.
2. `opencode export --sanitize` redacts prompts/titles/paths but preserves
   the full `tokens`/`modelID`/`providerID`/`time` structure — safe source
   for sharing sanitized examples.
3. The live DB is WAL-locked while OpenCode runs; direct reads fail with
   `database is locked (5)`. The collector must copy-then-read or use an
   immutable URI, and must never open the live file read-write.
4. `message.id` values are stable across scans (1731 rows, all distinct
   ids) — safe as the dedup/upsert key.

## 14. Sanitized example records

User message (no usage — never collected):

```json
{ "role": "user", "time": { "created": 1789532819759 },
  "agent": "build",
  "model": { "providerID": "opencode", "modelID": "big-pickle" } }
```

Assistant message (usage event — the collected record):

```json
{ "role": "assistant", "mode": "build", "agent": "build",
  "modelID": "big-pickle", "providerID": "opencode", "cost": 0,
  "tokens": { "total": 8297, "input": 6478, "output": 27,
              "reasoning": 0, "cache": { "read": 1792, "write": 0 } },
  "time": { "created": 1789532819792, "completed": 1789532824807 },
  "finish": "stop" }
```

Aborted message (zero-token event):

```json
{ "role": "assistant", "modelID": "union-alpha",
  "providerID": "opencode",
  "tokens": { "input": 0, "output": 0, "reasoning": 0,
              "cache": { "read": 0, "write": 0 } },
  "time": { "created": 1789580957878, "completed": 1789586181682 },
  "error": { "name": "MessageAbortedError" } }
```

## 15. Collector contract (what Phase 3 must implement)

- Source: `message` table in the SQLite file resolved via
  `opencode debug paths` (`data` line) + `/opencode.db`.
- Read pattern: copy-then-read or immutable URI; read-only.
- Collect: every row with `data.role = "assistant"` and `time.completed`
  present. Key: `message.id`. Fields per message: `providerID`, `modelID`
  (+`variant` metadata), `tokens.input/output` (+`reasoning`/`cache`
  metadata), `time.created` as UTC, `finish`/`error` to status mapping.
- Never sum `part` tokens or `session` rollups into totals.
- Cross-check: per-model sums should reconcile with
  `opencode stats --models` output.

*Clean-Code notes (ch08 Boundaries): the SQLite file plus the
`message.data` JSON shape are third-party boundaries — Phase 3 must wrap
them in a single adapter module (the OpenCode collector) exposing only the
normalized usage schema, with learning tests pinning the SQL/JSON shapes
documented above so an OpenCode upgrade that changes them fails fast in
tests, not silently in totals.*

