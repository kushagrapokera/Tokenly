# Cline CLI Integration — Implementation Plan

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

### Cline-Specific Tests

- [ ] Cline storage discovery.
- [ ] Historical session parsing.
- [ ] Model identification.
- [ ] Provider identification.
- [ ] Input token extraction.
- [ ] Output token extraction.
- [ ] Model switching.
- [ ] Multiple providers.
- [ ] Free and paid models where usage is available.
- [ ] Subagent accounting.
- [ ] Retry handling.
- [ ] Incomplete usage.
- [ ] Duplicate prevention.

### Shared Integration Tests

- [ ] OpenCode and Cline use the same database.
- [ ] Both use the same normalization pipeline.
- [ ] Both use the same aggregation logic.
- [ ] Platform filtering works.
- [ ] Combined totals are correct.
- [ ] Synchronization is independent per platform.
- [ ] Existing OpenCode history remains intact.
- [ ] Existing OpenCode tests continue passing.

## 12. Implementation Priority

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

## 13. Definition of Done

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

## 14. Final Instruction to the Coding Agent

**This task is an incremental integration into an existing codebase.**

Before writing code, inspect the repository and understand how OpenCode token tracking is currently implemented.

Reuse all compatible existing functionality.

Implement only the Cline-specific components and minimal shared changes required for compatibility.

Do not create parallel infrastructure for Cline.

Do not rewrite existing functionality merely to introduce a new platform.

If an existing component is too tightly coupled to OpenCode, refactor it into a shared component only when necessary, while preserving backward compatibility.

The desired result is:

**One unified token tracker with OpenCode and Cline CLI integrations, sharing the same database, processing pipeline, backend, analytics, and dashboard.**