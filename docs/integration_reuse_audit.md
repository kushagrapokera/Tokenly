# Integration Reuse Audit — Claude Code + Codex CLI

Phase 0 deliverable (implementation.md): an inventory of what exists, what each
component's reuse action is, and the minimum change set for adding Claude Code and
Codex CLI. Written before any production code.

Baseline verification: `pytest` — **447 passed, 1 skipped** on the untouched tree.

> **Historical.** This audit predates the dashboard rewrite. The `frontend/` React
> app it inventories below has been replaced by the dependency-free `web/` bundle
> served by `routes/dashboard.py`, so the frontend rows here no longer describe
> current files. The collector rows remain accurate.

---

## 1. Existing reusable files

### Shared infrastructure (adopted as-is)

| File | What it provides |
|---|---|
| `collectors/base.py` | `BaseCollector` ABC (`discover`, `collect_history`, `collect_updates`, `collect_scan`, `refresh`) and `ScanOutcome` (records + pending timestamps). Platform-agnostic already. |
| `collectors/checkpoint.py` | Millisecond checkpoint parse/serialize with `covers()` semantics (re-reads the boundary millisecond). Storage-agnostic. |
| `collectors/registry.py` | `build_collectors(settings)` — the single registration point. |
| `schemas/usage.py` | `UsageRecord` (platform, provider_id, model_id, session_id, message_id, source_event_id, timestamp, all token fields nullable, usage_status, overlap markers, raw_usage) and `DiscoveryResult`. |
| `normalization/normalizer.py` | `normalize_usage_record` / `normalize_timestamp` — the one entry point every collector already uses. |
| `normalization/totals.py` | `TokenCategories`, `calculate_totals` (total vs consumption), `read_count`. |
| `normalization/categories.py` | `CategoryRelationships`; per-platform constants `OPENCODE_RELATIONSHIPS`, `CLINE_RELATIONSHIPS`. |
| `normalization/status.py` | `resolve_usage_status` (reported / estimated / unavailable). |
| `database/models.py` | `UsageEvent` (unique `(platform, source_event_id)`) + `CollectorState`. Nullable token columns already present. |
| `database/repository.py` | `upsert_usage_records` (idempotent, batched), `count_usage_events`, `query_usage_events`, `sum_tokens`. |
| `database/schema.py`, `connection.py`, `state.py`, `types.py` | Schema bootstrap, engine/session factory, collector progress store. |
| `sync/service.py` | `SyncService` — checkpoint honored only after records commit, pending timestamps hold the checkpoint back, rescan overlap, nothing ever deleted. |
| `sync/coordinator.py` | Per-collector isolation (skip unavailable, one platform failing never blocks another). |
| `sync/factory.py` | `build_sync_service(collector, settings)` — shared SyncService wiring. |
| `sync/scheduler.py` | Startup history import + interval rescans in a worker thread. |
| `sync/result.py` | `SyncResult`. |
| `aggregation/*` (`filters`, `windows`, `ranges`, `summary`, `breakdown`, `timeline`) | Shared filtering (platform/provider/model), calendar windows, summaries, `(platform, provider, model)` breakdowns, timeline bucketing. |
| `routes/usage.py`, `routes/collector.py`, `routes/dependencies.py`, `routes/health.py` | Summary/daily/monthly/yearly/models/timeline endpoints; collector status + rescan endpoints (404 for unknown platform, listing is data-driven). |
| `main.py` | Composition root: builds collectors from the registry, wires scheduler/stat — no per-platform knowledge. |
| `config/settings.py` | Settings base; has per-platform knobs (`opencode_data_dir`, `cline_data_dir`) to extend the same way. |
| `errors/exceptions.py` | `CollectorError`, `CollectorSourceUnreadableError`, `UnsupportedStorageFormatError`, etc. |
| `collectors/opencode/snapshot.py` | `snapshot_database` context manager + `SnapshotCache` (SQLite WAL-aware copy). Reusable for any SQLite source. |
| `collectors/cline/snapshot.py` | Cline's equivalent (see note below on consolidation). |
| `logging_setup/`, `tests/` fixtures & builders | Standard patterns to copy for new collectors' tests. |

### Frontend

| File | Reuse action |
|---|---|
| `frontend/src/api/client.ts`, `types.ts`, `errors.ts` | REUSE — API layer is platform-agnostic. |
| `frontend/src/components/*` (metrics, charts, model table, tracking panel) | REUSE — all render data-driven lists. |
| `frontend/src/components/filterState.ts` | EXTEND — add `claude_code` / `codex` entries to `PLATFORM_LABELS` only. |

---

## 2. Classification per component

| Component | Action | Rationale |
|---|---|---|
| Collector interface (`collectors/base.py`) | REUSE | Accumulates everything the plan's Phase 1 requires, including `collect_scan` for in-flight work. |
| Checkpoints | REUSE | Timestamp-based; works for JSONL files as well as SQLite rows. |
| `UsageRecord` schema | REUSE | All Phase 1 required fields already exist and are nullable with None ≠ 0 semantics. |
| Database + repository | REUSE | Upsert keyed by `(platform, source_event_id)` is the dedup engine; no migration expected. |
| Normalization | REUSE | Entry point is source-agnostic; overlaps are per-platform data, not code. |
| `normalization/categories.py` | EXTEND | Add `CLAUDE_RELATIONSHIPS` (cache_* are subsets of input in Anthropic's reporting) and `CODEX_RELATIONSHIPS` after Phase 2/5 research verifies the actual semantics. No code change otherwise. |
| Deduplication (repository upsert) | REUSE | Nothing new needed; new platforms just choose stable `source_event_id`s. |
| Sync (service/coordinator/scheduler/factory) | REUSE | Zero changes; registration flows through automatically. |
| JSON/JSONL readers | NEW (shared) | Neither existing collector reads JSONL. Add one small `collectors/jsonl.py` utility shared by both new adapters (see §4). |
| Source snapshotting | REUSE / REFACTOR | `collectors/opencode/snapshot.py::_copy_database` + `_remove_snapshot` are generic; JSONL sources likely need no snapshot at all (files are append-only). |
| File monitoring / incremental scan | REUSE | Checkpoint + full re-read of changed sources is the established pattern; no watcher exists today and none is required. |
| Aggregation | REUSE | Filters already take `platform`; nothing platform-specific anywhere. |
| Backend API | REUSE | Routes enumerate collectors dynamically; status/rescan need no edits. |
| Dashboard | EXTEND | Two label entries + nothing else. |
| Registry (`collectors/registry.py`) | EXTEND | Two new lines in `build_collectors`. Settings knobs for custom data dirs. |
| Settings | EXTEND | `claude_data_dir`, `codex_data_dir` optional paths (mirrors existing pattern). |
| Claude Code adapter (locator/reader/extractor/collector) | NEW | No equivalent exists. Copy the structure of `collectors/cline` (per-platform package, boundary isolation). |
| Codex CLI adapter (locator/reader/extractor/collector) | NEW | No equivalent exists. Same approach. |
| Platform tests | NEW | Per-platform learning + unit + integration tests, following `tests/collectors/*` and `tests/integration/*` conventions. |

---

## 3. Compatibility risks

1. **Cumulative vs incremental counters (Codex).** `UsageRecord` assumes one row per
   event. Phase 5 must establish per-turn vs cumulative semantics before the
   extractor is written; the sync service does not dedup values, only identity, so a
   wrong choice inflates totals. Mitigation lives in the extractor, not the pipeline.
2. **Cache-token overlap (Claude).** `input_tokens` in Anthropic-style reporting
   typically *includes* cache reads; the pipeline handles `subset_of_input` already via
   `CategoryRelationships`, but the classification must be verified against real
   Claude Code records (Phase 2) before constant is added.
3. **Repeated message records (Claude).** Claude Code can rewrite one assistant
   message's JSONL line; `source_event_id` must remain stable across rewrites or the
   upsert will double count. The checkpoint boundary-re-read behavior (`covers()`)
   matches this well.
4. **`message_id` not unique on Claude/Codex like it is on OpenCode.** Cline already
   solved this with `namespaced_event_id` (`session:message`); both new adapters should
   follow that convention.
5. **Multi-line JSONL and archived sessions (Codex).** Sessions can exist in both
   `sessions/` and `archived_sessions/`; identity must be globally stable so the same
   session read from either location upserts once.
6. **Checkpoint semantics for file-based stores.** Cline (file-based) uses the same
   millisecond checkpoint; both new stores are also file-based with embedded
   timestamps, so this transfers. In-flight-message pending logic is OpenCode-specific
   and not expected to be needed — both new sources write completed usage.
7. **Migration risk.** None foreseen: no schema change is required. If Phase 2/5
   research demands extra metadata, it belongs in `raw_usage` (already a JSON column),
   not in a migration.

---

## 4. Minimum new files

```text
collectors/jsonl.py                     # shared JSONL reader helper (NEW)
collectors/claude/__init__.py
collectors/claude/locator.py            # ~/.claude/projects discovery (NEW)
collectors/claude/reader.py             # session JSONL decoding (NEW)
collectors/claude/extractor.py          # usage mapping + PLATFORM const (NEW)
collectors/claude/collector.py
collectors/codex/__init__.py
collectors/codex/locator.py             # ~/.codex/sessions + archived (NEW)
collectors/codex/reader.py
collectors/codex/extractor.py
collectors/codex/collector.py
tests/collectors/claude/*               # conftest builder + unit tests (NEW)
tests/collectors/codex/*
tests/integration/test_claude_pipeline.py
tests/integration/test_codex_pipeline.py
```

Modified existing files (small, backward-compatible):

```text
collectors/registry.py                  # +2 collector entries
config/settings.py                      # +2 optional data-dir knobs
normalization/categories.py             # +2 relationship constants (after Phase 2/5)
frontend/src/components/filterState.ts  # +2 label entries
```

Deliberately unchanged: `database/*`, `sync/*`, `aggregation/*`, `routes/*`,
`schemas/usage.py`, `collectors/base.py`, `main.py`.

---

## 5. Proposed implementation order

1. **Phase 1** — validate shared interfaces; nothing to change in schemas (confirm with
   the checklist in `docs/` after Phase 2/5 research).
2. **Phase 2** — Claude Code storage research (~/claude projects JSONL), verify field
   names, message rewriting, cache overlap against real records.
3. **Phase 3** — Claude collector + shared JSONL reader; integrate; Claude-specific
   tests.
4. **Phase 4** — Claude provider attribution (Anthropic/Bedrock/Vertex/OpenRouter/GLM/
   Kimi), verified against real metadata only.
5. **Phase 5** — Codex storage research (sessions + archived_sessions, event semantics).
6. **Phase 6** — Codex collector; cumulative-counter reconciliation rules decided here.
7. **Phase 7** — Codex provider attribution.
8. **Phase 8** — registry + settings registration; regression run.
9. **Phase 9** — frontend labels; verify dashboard renders both new platforms.
10. **Phase 10/11** — full regression + reuse review.

One platform at a time, Claude first (its storage is simpler and its overlap question
is the one the normalization module already anticipates).
