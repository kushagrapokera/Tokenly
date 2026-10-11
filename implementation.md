# Cline CLI Integration — Implementation Plan

> Collection performance, and how the design scales as more platforms are added,
> is worked out separately in [`parallelism.md`](parallelism.md).

## 1. Project Context

This project is an existing unified AI token usage tracker.

**OpenCode integration: DONE**

**Cline CLI integration: CURRENT TASK**

The goal is to add Cline CLI support to the existing application, not build a separate Cline token tracker.

The implementation must maximize code reuse and minimize changes to existing functionality.

## 2. Mandatory Development Rules

1. Do not create a new standalone application for Cline.
2. Do not create a separate backend.
3. Do not create a separate frontend.
4. Do not create a separate database.
5. Do not duplicate existing services or utilities.
6. Do not rewrite working OpenCode functionality unnecessarily.
7. Reuse existing abstractions wherever compatible.
8. Extend shared abstractions only when necessary.
9. Keep platform-specific parsing inside the Cline collector.
10. Preserve existing OpenCode behavior and data.
11. Do not introduce API keys or proxies.
12. Do not implement unrelated features.
13. Before creating a component, check whether equivalent functionality already exists.
14. Prefer minimal, backward-compatible changes.
15. Follow existing repository conventions and dependencies.

## 3. Phase 0 — Existing Codebase Audit

**Status: done.** The audit drove the design rather than producing a separate
assessment document; its conclusions are the reuse decisions recorded in
`docs/cline_storage_analysis.md` §15 and in the shared modules themselves.

**This phase is mandatory. Do not begin implementation before completing it.**

Inspect the existing repository and identify:

- Current OpenCode collector
- Collector interfaces or abstractions
- Token usage schema
- Token normalization logic
- Deduplication logic
- Database models
- Historical import functionality
- Synchronization and monitoring services
- Aggregation functions
- API endpoints
- Dashboard components
- Existing tests

For every component, classify it as:

- **REUSE:** Existing implementation works without changes.
- **EXTEND:** Existing implementation needs a small, backward-compatible modification.
- **NEW:** Cline-specific functionality does not exist.
- **REFACTOR:** Existing functionality is too tightly coupled to OpenCode and needs generalization.

Do not refactor unrelated code.

### Deliverable

Produce a short reuse assessment identifying:

- Files to reuse
- Files to modify
- New files required
- Existing functionality that must remain unchanged
- Potential regression risks

## 4. Phase 1 — Cline CLI Data Source Validation

**Status: done.** `docs/cline_storage_analysis.md`, verified against Cline CLI
3.0.70 on Linux.

Investigate Cline CLI's actual local storage for the supported installed version.

Determine:

- Active Cline data directory
- Session storage layout
- Message history format
- SQLite usage, if present
- Provider and model identifiers
- Input and output token fields
- Usage timestamps
- Stable usage identifiers
- Session summary versus per-message usage
- Reasoning and subagent token accounting

Prefer request-level usage records for model attribution.

Use session-level totals for validation or fallback, not as additional usage when corresponding request records have already been counted.

### Deliverable

Document the verified storage layout and token field mappings.

Do not assume that every Cline CLI version uses identical paths or schemas.

## 5. Phase 2 — Add the Cline Collector

**Status: done.** `collectors/cline/` (locator, snapshot, reader, extractor,
collector), registered in `collectors/registry.py` alongside OpenCode.

Create only the Cline-specific functionality necessary to extract usage records.

Required responsibilities:

- Discover Cline CLI storage.
- Read available session records.
- Read message usage metadata.
- Identify provider and model.
- Extract input and output tokens.
- Extract timestamps and source identifiers.
- Handle incomplete records.
- Convert source records into the existing shared collector format.

Reuse the existing collector interface.

Do not create another normalization engine, database service, or scheduler.

If the existing collector interface is OpenCode-specific, generalize it with minimal changes while preserving OpenCode behavior.

## 6. Phase 3 — Integrate With Shared Services

**Status: done, with no shared service changed.** Cline already fits the
existing abstractions, so nothing in normalization, deduplication, persistence,
synchronization, or aggregation needed extending. `tests/integration/` proves
it: `test_shared_pipeline.py` covers the cross-platform contract (one
database, one normalization, platform filtering, no id collisions) and
`test_cline_pipeline.py` drives a stand-in Cline store from source file to
aggregate for each risky case below.

Pass Cline usage records through the existing processing pipeline.

Reuse:

- Normalization
- Deduplication
- Database persistence
- Historical import
- Synchronization
- Aggregation

Only extend these services when Cline introduces a requirement they cannot currently handle.

Important cases:

- Multiple models in one session
- Provider-specific identifiers
- Streaming or updated usage records
- Retries
- Subagent usage
- Session-level versus request-level totals
- Overlapping token categories

Avoid double counting.

Preserve raw usage information where needed to support future compatibility.

## 7. Phase 4 — Extend Existing Database

**Status: done, with no schema change.** One `usage_events` table already holds
both platforms: `platform` plus the unique `(platform, source_event_id)`
constraint is what keeps Cline's `{session}:{message}` id from colliding with
OpenCode's bare `message.id`, and `usage_status` plus nullable counts is how
completeness is recorded. No column was missing, so no migration was written.

The audit turned up two defects that were fixed here:

- Nothing created the schema, so a fresh install answered `/api/health` with
  200 and then failed every usage query with `no such table: usage_events`.
  `database/schema.py` now prepares the schema at startup, creating only tables
  that are missing and never touching stored rows.
- `alembic/env.py` overwrote an explicitly supplied database URL with the one
  from settings, so migrations could only ever target the configured default.

`tests/test_schema_migrations.py` builds a database both ways — by running the
migrations and from the ORM metadata — and fails if the two ever disagree, which
is what would silently break existing installations after a model change.

Use the existing database and usage tables.

Check whether the current schema already supports:

- Multiple platforms
- Provider identifiers
- Model identifiers
- Session identifiers
- Stable usage event identifiers
- Input tokens
- Output tokens
- Timestamps
- Data completeness

If all fields exist, do not change the schema.

If fields are missing, introduce only the necessary backward-compatible migrations.

Preserve all existing OpenCode records.

Ensure Cline and OpenCode events cannot collide even if their source identifiers match.

## 8. Phase 5 — Extend Existing Synchronization

**Status: done.** Registration already existed; what was missing was anything to
*run* it. Starting the server previously imported nothing — collection happened
only when the rescan endpoint was called.

- `sync/coordinator.py` runs every registered collector, one platform at a time,
  each in its own session. A platform whose data is absent is skipped rather than
  recorded as an error, because not having Cline installed is a normal state. A
  platform that fails never stops the others.
- `sync/scheduler.py` runs a pass at startup and then on `sync_interval_seconds`.
  Scans run in a worker thread so a cold history cannot block the API, and
  shutdown is cooperative: the scheduler waits on an event, so closing the
  server neither waits out the interval nor starts another pass.
- The manual rescan endpoint is unchanged and still works alongside it.

Both settings (`sync_enabled`, `sync_interval_seconds`) exist so a test or a
headless run can turn automatic collection off.

Platforms were scanned sequentially in this phase. That was a safe first step, not
a settled design: only the *write* has to be serialised, since SQLite permits one
writer, and parallel collection is both safe and faster. Phase 9 tracks that
work.

Register the Cline collector with the existing collection mechanism.

Reuse existing:

- Startup discovery
- Historical scans
- Periodic reconciliation
- File monitoring, where applicable
- Synchronization checkpoints
- Error handling

Add only Cline-specific source discovery and change detection.

Ensure:

- Both collectors can operate independently.
- Failure in Cline collection does not stop OpenCode collection.
- Application restarts do not duplicate records.
- Imported history survives source deletion.

## 9. Phase 6 — Extend Existing Analytics

**Status: done, with one correction.** No Cline-specific aggregation was written.
The shared summary, timeline, and breakdown functions already read normalized rows
from any platform, and the API already accepted `platform`, `provider_id`, and
`model_id` on every usage endpoint, so all three views and all six metrics work
for Cline as they do for OpenCode.

What was wrong was the model breakdown's group key. It grouped by
`(provider_id, model_id)`, so two platforms serving the same model name would have
been merged into one row with no way to tell whose usage it was — the exact
attribution error the platform column exists to prevent, and the plan requires
platform in that table. The key is now `(platform, provider_id, model_id)` and
every breakdown row names its platform.

`tests/test_analytics_platforms.py` proves the three views and six metrics per
platform, that a breakdown reconciles with its summary, that unreported Cline
usage is surfaced as incomplete rather than counted as zero, and that bucketing
follows the requested timezone.

Measured against the live stores: Cline 189,250,734 tokens across 2,142 requests
with 28 unreported, matching its breakdown exactly, and the combined figure is
the sum of the two platforms.

Reuse all existing time-based and model-based aggregation logic.

Add platform filtering if not already supported.

Required views:

- OpenCode only
- Cline CLI only
- All supported platforms

Required metrics:

- Daily token usage
- Monthly token usage
- Yearly token usage
- All-time token usage
- Model-wise token usage
- Input and output token breakdown

Do not create Cline-specific aggregation functions if the existing shared aggregation functions can handle its normalized records.

## 10. Phase 7 — Extend Existing API and Dashboard

**Status: done, with three defects fixed.** The API needed nothing new — it
already accepted `platform` on every usage endpoint, and Phase 6 put the platform
in each model-breakdown row. The dashboard could not reach any of it.

- **Platform filter.** `filters.platform` existed in state and was already sent to
  the charts and the breakdown, but nothing could set it, so the page could only
  ever show combined totals. A platform dropdown was added beside the existing
  provider and model ones, deriving its options the same way they do: from the
  unfiltered model breakdown, so a newly added assistant appears without a
  frontend change.
- **Platform column in the model breakdown**, added to the row key so the same
  model name reached through two platforms stays two rows.
- **The headline cards ignored the filters entirely.** `MetricsCards` accepted
  only a timezone, so narrowing to one platform changed every chart and left the
  four big numbers showing all platforms — the figures looked at first were the
  ones ignoring the filter. The cards now carry the same platform, provider, and
  model filters as the panels below them.

Two further problems were found and fixed in passing. The tracking panel labelled
every collector's row "OpenCode", so Cline's row claimed OpenCode had been
detected; it now reads "Detection", with the platform named in its heading. And
platform display names were derived per component, so the filter dropdown and the
breakdown table could disagree about how a platform is spelled; both now use one
`platformLabel` helper that falls back to the raw id for a platform added later.

**Not built:** the platform comparison chart in plan §5.4. It is the one item
here needing new visualisation rather than wiring, and the per-platform filter
plus the breakdown column cover the same need for now.

Reuse the existing API endpoints and dashboard components.

Modify only what is necessary to:

- Display Cline as a supported platform.
- Filter usage by platform.
- Show combined OpenCode and Cline totals.
- Display Cline collector status.
- Show model-wise Cline usage.

Do not create separate Cline pages unless the existing interface cannot reasonably represent the required information.

Preserve current OpenCode dashboard behavior.

## 11. Phase 8 — Testing and Regression Validation

**Status: done.** Every item below was audited against the tests that actually
exist rather than assumed. Each was already covered except the two marked
**new**, which were written for this phase because they were implied rather than
stated: free and paid models being treated identically (plan §4.4), and both
collectors demonstrably sharing one normaliser (Phase 3). Both are now mutation-
checked — dropping a free-tier model or folding Cline's cache into its per-call
total each fails the suite.

### Cline-Specific Tests

- [x] Cline storage discovery. → `test_locator.py`, `test_discovery_works_without_a_session_index`
- [x] Historical session parsing. → `test_history_returns_one_record_per_assistant_message`
- [x] Model identification. → `test_record_carries_provider_model_and_session_identity`
- [x] Provider identification. → same, plus `test_two_providers_serving_one_model_name_stay_distinct`
- [x] Input token extraction. → `test_token_fields_follow_the_phase_1_field_map`
- [x] Output token extraction. → same
- [x] Model switching. → `test_model_switching_attributes_each_record_to_its_own_model`
- [x] Multiple providers. → `test_multiple_models_in_one_session_stay_separate`, and the two-provider case above
- [x] **Free and paid models where usage is available.** → **new**: `test_phase8_checklist.py`
- [x] Subagent accounting. → `test_a_subagent_session_is_attributed_to_its_own_session_and_model`
- [x] Retry handling. → `test_a_retried_call_keeps_the_failure_and_the_success_apart`
- [x] Incomplete usage. → `test_error_display_is_stored_as_unavailable`, `test_missing_usage_is_stored_as_unknown_and_kept_out_of_totals`
- [x] Duplicate prevention. → `test_resume_duplicate_ids_stay_distinct_per_session`, `test_a_resumed_session_copy_is_stored_separately_without_double_counting`

### Shared Integration Tests

- [x] OpenCode and Cline use the same database. → `test_both_collectors_share_one_database`
- [x] Both use the same normalization pipeline. → **new**: `test_identical_usage_normalizes_identically_on_both_platforms`, and the cache and missing-usage cases beside it
- [x] Both use the same aggregation logic. → `test_platform_filtering_separates_the_two_sources`, `test_analytics_platforms.py`
- [x] Platform filtering works. → `test_the_combined_view_adds_both_platforms` and the per-platform cases
- [x] Combined totals are correct. → `test_each_platform_can_be_viewed_on_its_own`, `test_the_model_breakdown_reconciles_with_the_combined_summary`
- [x] Synchronization is independent per platform. → `test_each_platform_resumes_from_its_own_checkpoint`, `test_a_failing_collector_does_not_stop_the_others`
- [x] Existing OpenCode history remains intact. → `test_cline_sync_leaves_opencode_history_intact`
- [x] Existing OpenCode tests continue passing. → 412 backend tests, green on every commit

**Not covered, deliberately.** No test runs both collectors against the *live*
stores on every run — those are the learning tests, which skip when a store is
absent so the suite stays green on a machine without both assistants. The
cross-platform guarantees are therefore proven against stand-in stores, which is
what makes them deterministic.

## 12. Phase 9 — Collection Performance

**Status: A0–A3 done.** The design, the measurements behind it, and the rollout
order are in [`parallelism.md`](parallelism.md).

Scope in one line: make a collection pass cheap enough that the sync interval can
drop from five minutes to about one, without changing what is stored.

- **A0 — done.** OpenCode was running `opencode debug paths` on every scan and
  every status view, spending ~590 ms asking where a directory is. The answer is
  now resolved once per collector and reused. Measured: an OpenCode scan went
  from **900 ms to 276 ms**, and the collector status endpoint from 759 ms to
  194 ms.
- **A1 — done.** Re-importing history issued one `UPDATE` per row, costing
  1,125 ms for 2,142 records. The whole batch now goes out as a single
  `INSERT … ON CONFLICT DO UPDATE`, measured at **71 ms** — a sixteen-fold
  improvement on the path a manual rescan pays every time.
- **A2 — done.** Every scan copied OpenCode's whole database before reading it
  (~172 ms). The copy is now reused while the source is unchanged: the tracking
  status view went from **194 ms to 7 ms**. The fingerprint includes the
  write-ahead log, because OpenCode runs in WAL mode and new usage lands there
  while the main file looks untouched — ignoring that would reuse a copy missing
  the very records it was asked to find.
- **A3 — done.** The daily timeline took 43 ms because finding a row's bucket
  scanned every bucket edge from the start, once per row. A binary search over the
  same edges brought it to **8.2 ms**, with buckets identical before and after,
  including across daylight-saving transitions.
- **Phase B — held.** Parallel collection across Cline's batches. Held on
  2026-10-12 at the owner's direction, after the gate came out against it: with
  phase A complete a full collection pass costs 206 ms, and B would save about
  43 ms of that — in exchange for a process pool, a batching contract, a
  single-writer commit barrier and a conformance suite, permanently. The design
  is ready and nothing in it has been disproved; the conditions that would
  reopen it are recorded in `parallelism.md` §13.

**Where phase 9 leaves things.** Collection, both platforms, measured on the live
stores: **948 ms → 206 ms**. Status view when idle: **759 ms → 7 ms**. Re-importing
5,053 records: **~2,600 ms → 169 ms**. None of it needed parallelism — phase A
removed fixed per-scan cost, which is what actually dominated.

## 13. Implementation Priority

| Priority | Task | Action |
|---|---|---|
| P0 | Audit existing repository | Inspect |
| P0 | Validate Cline storage | Research |
| P0 | Cline collector | New |
| P0 | Token mapping | New adapter / reuse shared normalization |
| P0 | Shared persistence | Reuse / extend |
| P0 | Deduplication | Reuse / extend |
| P0 | Synchronization | Reuse / extend |
| P0 | Usage aggregation | Reuse |
| P1 | API platform support | Reuse / extend |
| P1 | Dashboard platform support | Reuse / extend |
| P0 | Cline and OpenCode regression tests | Extend |
| P1 | Collection performance | Phase A done; phase B held — [`parallelism.md`](parallelism.md) |

## 14. Definition of Done

Cline integration is complete when:

- [ ] Cline CLI usage is collected automatically.
- [ ] Available historical usage is imported.
- [ ] Token counts are attributed to the correct models.
- [ ] Multiple providers are supported.
- [ ] Daily, monthly, yearly, and all-time totals work.
- [ ] Cline usage appears in the existing dashboard.
- [ ] Combined OpenCode and Cline totals work.
- [ ] Existing shared components are reused wherever compatible.
- [ ] No unnecessary duplicate services are introduced.
- [ ] No separate application or database is created.
- [ ] No API keys or proxy configuration are required.
- [ ] Existing OpenCode functionality remains intact.
- [ ] Regression tests pass.

## 15. Final Instruction to the Coding Agent

**This task is an incremental integration into an existing codebase.**

Before writing code, inspect the repository and understand how OpenCode token tracking is currently implemented.

Reuse all compatible existing functionality.

Implement only the Cline-specific components and minimal shared changes required for compatibility.

Do not create parallel infrastructure for Cline — meaning a Cline-only fork of
something that already exists. Shared infrastructure that every platform uses is
the opposite of that, and is what Phase 9 adds.

Do not rewrite existing functionality merely to introduce a new platform.

If an existing component is too tightly coupled to OpenCode, refactor it into a shared component only when necessary, while preserving backward compatibility.

The desired result is:

**One unified token tracker with OpenCode and Cline CLI integrations, sharing the same database, processing pipeline, backend, analytics, and dashboard.**