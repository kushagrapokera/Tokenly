# Phase 1 — Shared Compatibility Assessment: Claude Code + Codex CLI

Deliverable for Phase 1 of `implementation.md`. Verifies the existing collector
system can represent Claude Code and Codex CLI usage **without new infrastructure**.

Companion to `docs/integration_reuse_audit.md` (Phase 0). Written after the audit,
before any adapter code.

---

## 1. Required shared fields vs `schemas/usage.UsageRecord`

| Required field (plan Phase 1) | `UsageRecord` field | Status |
|---|---|---|
| Platform identifier | `platform` | ✅ free string; no enum to extend |
| Provider identifier | `provider_id` | ✅ |
| Model identifier | `model_id` | ✅ |
| Session identifier | `session_id` | ✅ |
| Source usage event identity | `source_event_id` (+`message_id`) | ✅ unique per `(platform, source_event_id)` in `usage_events` |
| Timestamp | `timestamp` (UTC-aware) | ✅ |
| Input / output / total tokens | `input_tokens` / `output_tokens` / `total_tokens` | ✅ all nullable |
| Extra categories | `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`, `consumption_tokens` | ✅ already present |
| Usage completeness/status | `usage_status` (`reported` / `estimated` / `unavailable`) | ✅ |
| Source revision metadata (optional) | `raw_usage` (JSON, preserved verbatim) | ✅ |
| Overlap correctness (optional) | `cache_overlap`, `reasoning_overlap` | ✅ per-platform, data-driven |

**Verdict: the existing schema is sufficient. No migration.**

---

## 2. Task-by-task verification

Each Phase 1 checklist item, with the evidence that already exists:

| Task | Verdict | Evidence |
|---|---|---|
| Usage schema compatibility | ✅ pass-through | `platform` is unvalidated text; both new ids fit. Verified live by `tests/integration/test_phase1_compatibility.py`. |
| Platform-specific event identity | ✅ works with existing upsert | Dedup key = `(platform, source_event_id)`. Cline already namespaces ids as `session:message` (`collectors/cline/extractor.py::namespaced_event_id`) because bare `message.id` collides across sessions. Claude Code and Codex must choose stable ids the same way (Claude: JSONL `uuid`/message id per session; Codex: rollout event id per session). No pipeline change needed — this is an adapter decision recorded here. |
| Nullable token fields | ✅ proven | `None` ≠ 0 enforced end to end: `normalization/totals.read_count` returns `None`, repository stores NULL, aggregation counts `unknown_total_events` (`aggregation/summary.py`). Tested in `tests/test_phase8_checklist.py`, `tests/test_scenarios.py::test_a_missing_usage_message_does_not_zero_out_a_real_total`. |
| Model/provider attribution | ✅ | Breakdown groups by `(platform, provider_id, model_id)` — `aggregation/breakdown.py`. Third-party providers (OpenRouter → DeepSeek/GLM/Kimi) are just `provider_id="openrouter", model_id="deepseek/..."` values. Records that cannot attribute a model will use `"unknown"` as the model id — the schema accepts it and the dashboard shows it honestly. |
| Timestamp normalization | ✅ | `normalization.normalize_timestamp` forces aware UTC; calendar boundaries are resolved later per-user timezone in `aggregation/ranges`. Both sources store UTC epoch ms/ISO, which the adapters convert before reaching the normalizer. |
| Incremental record updates | ✅ | Upsert updates in place on the same `(platform, source_event_id)`; checkpoint boundary millisecond is re-read on every scan (`collectors/checkpoint.py::Checkpoint.covers`). Proven for a rewritten row by `test_scenarios.py::test_a_retried_request_updates_its_row_rather_than_adding_one`. |
| Historical reconciliation | ✅ | `SyncService.run(from_scratch=True)` re-reads everything idempotently; `test_scenarios.py::test_repeated_runs_and_restarts_never_inflate_a_total`. |
| Source data deletion | ✅ | Repository has no delete path; `test_scenarios.py::test_deleting_the_entire_source_leaves_stored_usage_intact`, `tests/test_database.py::test_no_repository_call_deletes_events`. |
| Dashboard platform filtering | ✅ | `UsageFilter(platform=...)` applies to every aggregation and endpoint; a platform with no rows returns zeroes, not an error — already tested for the literal platform id `"codex"` in `test_analytics_platforms.py::test_a_platform_with_no_usage_reports_zeroes_rather_than_failing`. |

---

## 3. Rules honored

- **No new schema** — none needed (§1).
- **No migration** — `alembic/versions/` untouched; `tests/test_schema_migrations.py` keeps
  guarding models-vs-migrations equality.
- **No OpenCode/Cline collector refactor** — the audit's conclusion stands: the two
  adapters copy the *structure* of `collectors/cline` (locator / reader / extractor /
  collector) but do not touch its code.

## 4. Adapter-level decisions fixed by this phase (not pipeline changes)

1. `source_event_id` must be globally stable per platform and unique per session:
   `<session_id>:<message_id>` (Cline's convention), because both new sources can
   repeat message ids across sessions.
2. Usage arriving before model context is known (Codex `token_count` events without a
   preceding `turn_context`) must still be stored with `model_id="unknown"` and
   `usage_status="reported"` — honesty over attribution. This is what Phase 5 will pin
   against the real rollout format.
3. Cumulative counters (Codex `total_token_usage`) are never stored as events; the
   adapter derives per-event usage or stores only authoritative increments (Phase 5/6).
4. Overlap constants (`CLAUDE_RELATIONSHIPS`, `CODEX_RELATIONSHIPS`) are additions to
   `normalization/categories.py` only after Phase 2/5 research verifies the semantics —
   the pipeline already supports any `subset_of_input` classification.

## 5. Machine verification

`tests/integration/test_phase1_compatibility.py` proves the shared pipeline accepts the
two new platform identifiers today: synthetic records with `platform="claude_code"`
and `platform="codex"` flow through normalization → upsert → aggregation with correct
totals, platform filtering, unknown-token honesty, and collision safety with the
existing platforms.
