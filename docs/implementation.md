# Universal AI Token Tracker — implementation_plan.md

**Project:** Universal AI Token Usage Tracker  
**Implementation Type:** Incremental integration into an existing application  
**Current Scope:** Claude Code + Codex CLI  
**Primary Requirement:** Maximum code reuse, minimum new code

---

## 1. Project Status

| Platform | Status | Required Action |
|---|---|---|
| OpenCode | COMPLETED | Preserve and reuse |
| Cline CLI | COMPLETED | Preserve and reuse |
| Claude Code | TO IMPLEMENT | Add platform adapter |
| Codex CLI | TO IMPLEMENT | Add platform adapter |
| Antigravity | FUTURE | No implementation |
| FreeBuff | FUTURE | No implementation |

OpenCode and Cline CLI are already implemented.

The existing application, database, backend, analytics, and dashboard must be retained.

**Do not create separate applications for Claude Code and Codex CLI.**

---

## 2. Mandatory Engineering Principles

The implementation must follow these rules:

1. Reuse existing code before writing new code.
2. Inspect the complete relevant codebase before implementation.
3. Avoid duplicate collectors, services, utilities, and database models.
4. Use the existing database.
5. Use the existing backend.
6. Use the existing frontend.
7. Use the existing token normalization and aggregation services.
8. Use the existing synchronization mechanism wherever compatible.
9. Preserve all existing OpenCode and Cline CLI functionality.
10. Introduce only platform-specific parsing and discovery logic.
11. Extend shared interfaces only when necessary.
12. Prefer small, backward-compatible changes.
13. Avoid introducing new dependencies when existing libraries are sufficient.
14. Do not create platform-specific analytics pipelines.
15. Do not modify users' Claude Code or Codex CLI configurations.
16. Do not require API keys or proxy servers.
17. Do not read or persist credentials.
18. Do not implement unrelated features.
19. Do not rewrite working code merely for stylistic consistency.
20. Validate every change against existing regression tests.

**Core rule: Before creating a new component, search the repository for equivalent functionality and reuse it if compatible.**

---

## 3. Target Architecture

The application must continue using its existing shared infrastructure.

```text
                  Universal Token Tracker
                            |
                Existing Collector Interface
                            |
         +------------------+------------------+
         |                  |                  |
     OpenCode            Cline CLI        New Collectors
      DONE                DONE                  |
                                      +---------+---------+
                                      |                   |
                                Claude Code          Codex CLI
                                  Adapter              Adapter
                                      |                   |
                                      +---------+---------+
                                                |
                                   Existing Shared Pipeline
                                                |
                                       Token Normalization
                                                |
                                         Deduplication
                                                |
                                         Persistence
                                                |
                                         Aggregation
                                                |
                                       Existing Backend
                                                |
                                       Existing Dashboard
```

The new adapters should produce the same normalized usage representation already accepted by the application.

If the existing interface is insufficient, extend it rather than building an independent pipeline.

---

# Phase 0 — Existing Repository Audit

**Priority: P0 — Mandatory**

## Objective

Identify exactly which components are already implemented and determine the minimum required changes.

Do not write production code before completing this phase.

### Inspect

- OpenCode collector
- Cline CLI collector
- Shared collector interface
- Platform registration
- Storage discovery utilities
- JSON/JSONL readers
- SQLite access utilities
- Token normalization
- Deduplication
- Historical import
- Incremental synchronization
- Database schema
- Aggregation functions
- Backend API
- Dashboard components
- Test utilities

### Reuse Classification

For every relevant component, assign one of these actions:

| Classification | Meaning |
|---|---|
| REUSE | Works without modification |
| EXTEND | Small backward-compatible change |
| REFACTOR | Generalize existing platform-specific code |
| NEW | Functionality does not already exist |

### Expected Reuse

| Component | Preferred Action |
|---|---|
| Collector interface | REUSE |
| JSON/JSONL utilities | REUSE |
| Database | REUSE |
| Token schema | REUSE |
| Normalization | REUSE / EXTEND |
| Deduplication | REUSE / EXTEND |
| Historical sync | REUSE |
| File monitoring | REUSE / EXTEND |
| Aggregation | REUSE |
| Backend API | REUSE / EXTEND |
| Dashboard | REUSE / EXTEND |
| Claude-specific parser | NEW |
| Codex-specific parser | NEW |
| Platform-specific tests | NEW |

### Deliverable

Create `docs/integration_reuse_audit.md` containing:

- Existing reusable files
- Existing functions and classes to reuse
- Files requiring modification
- Minimum new files
- Compatibility risks
- Proposed implementation order

### Exit Criteria

The implementation scope is reduced to the smallest practical set of changes.

---

# Phase 1 — Shared Compatibility Assessment

**Priority: P0**

## Objective

Ensure the existing collector system can represent Claude Code and Codex CLI usage without creating duplicate infrastructure.

### Required Shared Fields

The existing usage representation should support:

- Platform identifier
- Provider identifier
- Model identifier
- Session identifier
- Source usage event identifier
- Timestamp
- Input tokens
- Output tokens
- Total tokens
- Usage completeness/status

Additional optional metadata may be needed for source revisions and token accounting.

### Tasks

- [ ] Verify existing usage schema compatibility.
- [ ] Verify platform-specific event identity.
- [ ] Verify nullable token fields.
- [ ] Verify model/provider attribution.
- [ ] Verify timestamp normalization.
- [ ] Verify incremental record updates.
- [ ] Verify historical reconciliation.
- [ ] Verify source data deletion behavior.
- [ ] Verify dashboard platform filtering.

### Rules

Do not introduce a new schema if the existing schema is sufficient.

Do not migrate the database unnecessarily.

Do not refactor the OpenCode and Cline collectors unless a shared interface change genuinely requires it.

### Exit Criteria

Both new collectors can integrate with the existing shared processing pipeline.

---

# Phase 2 — Claude Code Storage Discovery and Research

**Priority: P0**

## Objective

Validate the local data sources used by the installed Claude Code version.

### Candidate Data Sources

Claude Code commonly persists session histories under:

`~/.claude/projects/`

Sessions may be stored as JSONL files containing message metadata.

Potential usage fields include:

- `message.model`
- `message.usage.input_tokens`
- `message.usage.output_tokens`
- `message.usage.cache_creation_input_tokens`
- `message.usage.cache_read_input_tokens`
- `message.id`
- Session identifiers
- Timestamps

These fields must be validated against actual records.

### Tasks

- [ ] Detect Claude Code installation.
- [ ] Detect active Claude data directory.
- [ ] Discover available project sessions.
- [ ] Identify JSONL session files.
- [ ] Identify assistant message usage records.
- [ ] Identify model identifiers.
- [ ] Identify stable message identifiers.
- [ ] Identify usage timestamps.
- [ ] Determine repeated-message behavior.
- [ ] Investigate subagent sessions.
- [ ] Investigate model switching.
- [ ] Investigate third-party provider attribution.
- [ ] Verify cache-token accounting.
- [ ] Identify version-specific differences.

### Privacy Requirements

Only extract the fields needed for usage analytics.

Do not store:

- Prompt text
- Model response text
- Tool call arguments
- Source code
- Credentials

### Exit Criteria

Claude Code's usage source and token accounting behavior are verified.

---

# Phase 3 — Claude Code Adapter

**Priority: P0**

## Objective

Add a minimal Claude Code collector using existing interfaces.

### Proposed Responsibilities

The adapter should only:

1. Discover Claude Code session data.
2. Read relevant usage records.
3. Extract model and provider metadata.
4. Extract token counts.
5. Extract timestamps and stable identifiers.
6. Return records compatible with the existing shared pipeline.

### Preferred Reuse

Reuse the existing:

- Collector base class
- JSONL reader, if present
- Filesystem scanner
- Incremental synchronization
- Token normalizer
- Deduplication engine
- Database persistence

### Claude-Specific Considerations

**Repeated message records**

Claude Code may persist multiple records associated with one assistant response.

Use stable request/message identity and update or merge usage appropriately.

Do not count the same model request multiple times.

**Model switching**

Attribute each request to its actual model, not only the session's default model.

**Cache tokens**

Claude Code can report cached input separately.

The shared accounting policy must explicitly decide how cached input contributes to the overall input and total token metrics.

Do not omit tokens simply because they were served from cache.

Do not count overlapping categories twice.

**Subagents**

Identify subagent sessions and count their actual model requests once.

### Exit Criteria

Claude Code usage passes through the existing pipeline and appears in the existing database.

---

# Phase 4 — Claude Code Provider Compatibility

**Priority: P1**

## Objective

Support native and compatible third-party provider configurations.

### Target Providers

- Anthropic
- OpenRouter
- Amazon Bedrock
- Google Vertex AI
- DeepSeek
- GLM / Z.AI
- Kimi / Moonshot
- Other compatible gateways

### Important Distinction

The provider configured by Claude Code is not necessarily the company that originally developed the model.

For example:

- Platform: Claude Code
- Gateway: OpenRouter
- Model: DeepSeek

Preserve the gateway/provider separately from the model identifier whenever possible.

### Provider Detection Rules

1. Prefer explicit provider metadata.
2. Use documented non-secret configuration metadata when reliable.
3. Do not inspect credential values.
4. Do not assume provider from model name alone.
5. Do not assume a model is served directly by its developer.
6. Use `unknown` when reliable attribution is unavailable.

If a gateway can route requests to multiple upstream providers, distinguish the configured gateway from the actual upstream provider when both are available.

Do not invent upstream provider attribution.

### Implementation Requirements

- [ ] Reuse existing provider normalization.
- [ ] Add mappings only when necessary.
- [ ] Preserve unknown providers.
- [ ] Support native Claude models.
- [ ] Support compatible third-party models.
- [ ] Test provider/model switching.
- [ ] Handle missing provider metadata.

### Exit Criteria

Claude Code usage is attributed to the correct platform, known gateway/provider, and model without requiring credentials.

---

# Phase 5 — Codex CLI Storage Discovery and Research

**Priority: P0**

## Objective

Validate Codex CLI's local session storage and usage reporting.

### Candidate Data Sources

Codex CLI commonly stores session records under:

`~/.codex/sessions/`

Archived sessions may also exist under:

`~/.codex/archived_sessions/`

Session rollout files may contain JSONL events.

Relevant event structures may include:

- `event_msg`
- `token_count`
- `last_token_usage`
- `total_token_usage`
- `turn_context`
- Model metadata
- Session timestamps

The exact fields and event semantics must be validated against the installed Codex version.

### Tasks

- [ ] Detect Codex CLI installation.
- [ ] Detect active Codex home directory.
- [ ] Discover active sessions.
- [ ] Discover archived sessions.
- [ ] Identify token usage events.
- [ ] Identify cumulative token counters.
- [ ] Identify per-turn token counters.
- [ ] Identify model context events.
- [ ] Identify provider configuration metadata.
- [ ] Identify session identifiers.
- [ ] Identify usage timestamps.
- [ ] Investigate model switching.
- [ ] Investigate retry and compaction behavior.
- [ ] Validate duplicate handling across active and archived records.

### Critical Accounting Rule

Do not add cumulative session totals to individual turn usage.

If both cumulative and per-turn usage are available, choose a consistent authoritative source and use the other for reconciliation.

### Exit Criteria

Codex usage event semantics and model attribution are verified.

---

# Phase 6 — Codex CLI Adapter

**Priority: P0**

## Objective

Implement the smallest possible Codex-specific collector.

### Responsibilities

The adapter should:

1. Discover Codex session files.
2. Read relevant rollout events.
3. Extract token usage.
4. Identify the active model for each usage event.
5. Identify provider metadata where available.
6. Extract stable source identifiers.
7. Normalize event timestamps.
8. Pass usage records to the existing shared pipeline.

### Reuse Requirements

Reuse:

- Existing collector interface
- JSONL utilities
- Incremental file scanning
- Shared normalization
- Shared deduplication
- Shared persistence
- Shared aggregation

### Codex-Specific Considerations

**Cumulative token counters**

Determine whether `last_token_usage` is available and reliable.

If only cumulative usage exists, derive nonnegative increments only when the source semantics and counter continuity are verified.

Handle counter resets and missing events without fabricating usage.

**Model attribution**

Associate usage with the correct model context.

If model context is missing, preserve the usage but mark model attribution as unknown.

**Archived sessions**

Avoid counting a session twice when records exist in multiple locations.

**Compaction and retries**

Ensure that compaction, resumed sessions, and repeated token events do not inflate totals.

### Exit Criteria

Codex CLI usage is collected through the existing pipeline and stored in the existing database.

---

# Phase 7 — Codex CLI Provider Compatibility

**Priority: P1**

## Objective

Support native OpenAI models and compatible third-party providers.

### Target Providers

- OpenAI
- OpenRouter
- DeepSeek
- GLM / Z.AI
- Kimi / Moonshot
- Compatible OpenAI-style gateways
- Compatible local model providers

### Requirements

- [ ] Detect configured provider metadata where reliable.
- [ ] Preserve original model identifiers.
- [ ] Support model switching.
- [ ] Support provider switching.
- [ ] Handle provider aliases.
- [ ] Reuse existing provider normalization.
- [ ] Avoid provider inference based only on model names.
- [ ] Avoid credential collection.
- [ ] Preserve unknown provider values.

### Compatibility Rule

Do not assume that every provider exposes the same token usage fields.

The tracker must use the token information recorded by Codex and label missing or incomplete usage appropriately.

### Exit Criteria

Codex native and supported third-party usage is correctly attributed wherever reliable metadata exists.

---

# Phase 8 — Shared Database and Synchronization

**Priority: P0**

## Objective

Register Claude Code and Codex CLI with the existing persistence and synchronization infrastructure.

### Database

Reuse the existing database.

Only introduce migrations if necessary.

Do not create:

- A Claude-only database
- A Codex-only database
- Separate usage tables without a demonstrated need
- Duplicate persistence services

### Synchronization

Reuse existing:

- Historical import
- File monitoring
- Periodic reconciliation
- Sync checkpoints
- Error recovery
- Record upserts

### Tasks

- [ ] Register Claude collector.
- [ ] Register Codex collector.
- [ ] Preserve existing OpenCode registration.
- [ ] Preserve existing Cline registration.
- [ ] Support independent collector failures.
- [ ] Support historical backfill.
- [ ] Support incremental updates.
- [ ] Prevent duplicate records.
- [ ] Preserve imported history after source deletion.

### Exit Criteria

All four collectors use the same storage and synchronization infrastructure.

---

# Phase 9 — Shared Analytics, API, and Dashboard

**Priority: P1**

## Objective

Expose Claude Code and Codex usage through the existing analytics system.

### Reuse Requirements

Reuse existing:

- Daily aggregation
- Monthly aggregation
- Yearly aggregation
- All-time aggregation
- Model breakdown
- Provider breakdown
- Platform breakdown
- Date filtering
- API endpoints
- Dashboard charts

### Required Changes

Only add functionality that is currently missing:

- Claude Code platform registration
- Codex CLI platform registration
- Platform filter options
- Collector status indicators
- Provider/model display compatibility

### Dashboard Requirements

The existing dashboard must display:

- OpenCode
- Cline CLI
- Claude Code
- Codex CLI
- Combined token consumption

Do not build separate dashboards for Claude and Codex.

### Exit Criteria

All four platforms are visible in the existing dashboard, with correct combined and filtered totals.

---

# Phase 10 — Testing and Regression Validation

**Priority: P0 before release**

## Claude Code Tests

- [ ] Default storage discovery.
- [ ] Custom storage discovery.
- [ ] JSONL parsing.
- [ ] Historical import.
- [ ] Input/output token extraction.
- [ ] Cache accounting.
- [ ] Duplicate message handling.
- [ ] Model switching.
- [ ] Provider switching.
- [ ] Subagent usage.
- [ ] Missing usage fields.
- [ ] Interrupted sessions.

## Codex CLI Tests

- [ ] Default storage discovery.
- [ ] Custom storage discovery.
- [ ] Active session parsing.
- [ ] Archived session parsing.
- [ ] Token event parsing.
- [ ] Cumulative counter handling.
- [ ] Per-turn usage handling.
- [ ] Model context attribution.
- [ ] Provider identification.
- [ ] Model switching.
- [ ] Session compaction.
- [ ] Retry handling.
- [ ] Duplicate prevention.

## Shared Regression Tests

- [ ] OpenCode remains functional.
- [ ] Cline CLI remains functional.
- [ ] Existing data is preserved.
- [ ] All collectors share the same database.
- [ ] All collectors use shared normalization.
- [ ] All collectors use shared deduplication.
- [ ] All collectors use shared aggregation.
- [ ] Combined totals are correct.
- [ ] Platform filters are correct.
- [ ] Model filters are correct.
- [ ] Provider filters are correct.
- [ ] Application restarts do not duplicate records.

### Exit Criteria

All critical tests pass, and existing integrations remain functional.

---

# Phase 11 — Final Optimization and Release

**Priority: P1**

## Objective

Minimize maintenance overhead and release Claude Code + Codex CLI support.

### Code Reuse Review

Before release, verify:

- No duplicate normalization engine was created.
- No duplicate deduplication engine was created.
- No duplicate database was created.
- No duplicate API layer was created.
- No duplicate dashboard was created.
- Existing utilities were reused where compatible.
- Platform-specific logic remains isolated.
- Shared changes are backward-compatible.
- New dependencies are justified.
- Unnecessary abstractions were avoided.

### Release Requirements

- [ ] Automatic Claude Code detection.
- [ ] Automatic Codex CLI detection.
- [ ] Historical usage import.
- [ ] Incremental usage tracking.
- [ ] Native model support.
- [ ] Compatible third-party provider support.
- [ ] Accurate token totals.
- [ ] Unified dashboard.
- [ ] Local-only operation.
- [ ] No provider API keys required.
- [ ] No configuration changes required.
- [ ] Existing integrations preserved.

---

## 4. Recommended Implementation Order

| Order | Work | Code Strategy |
|---|---|---|
| 1 | Audit existing codebase | Inspect, don't rebuild |
| 2 | Validate shared interfaces | Reuse or minimally extend |
| 3 | Research Claude storage | Verify data source |
| 4 | Add Claude collector | Minimal new adapter |
| 5 | Validate Claude providers | Reuse shared provider logic |
| 6 | Research Codex storage | Verify event semantics |
| 7 | Add Codex collector | Minimal new adapter |
| 8 | Validate Codex providers | Reuse shared provider logic |
| 9 | Register both collectors | Reuse existing synchronization |
| 10 | Update dashboard | Extend existing UI |
| 11 | Run regression tests | Preserve completed integrations |
| 12 | Release | One unified application |

---

## 5. Minimum New Components

The expected new code should primarily consist of:

**Claude Code**

- Storage discovery
- Session JSONL parsing
- Claude-specific usage mapping
- Provider metadata extraction
- Tests

**Codex CLI**

- Storage discovery
- Rollout JSONL parsing
- Token event interpretation
- Model/provider context extraction
- Tests

**Shared changes only when necessary**

- Collector registration
- Additional token field handling
- Provider metadata normalization
- Platform filtering
- Compatibility migrations

The exact files and line count depend on the existing repository.

Do not create new files merely to match this suggested organization if the existing structure already supports the functionality.

---

## 6. Definition of Done

The implementation is complete when:

- [ ] OpenCode remains completed and functional.
- [ ] Cline CLI remains completed and functional.
- [ ] Claude Code usage is automatically collected.
- [ ] Codex CLI usage is automatically collected.
- [ ] Historical usage is imported where available.
- [ ] Native models are tracked.
- [ ] Compatible third-party providers are tracked.
- [ ] Daily, monthly, yearly, and all-time usage works.
- [ ] Platform-wise usage works.
- [ ] Provider-wise usage works.
- [ ] Model-wise usage works.
- [ ] Duplicate counting is prevented.
- [ ] Existing shared components are reused.
- [ ] No parallel infrastructure is introduced. *(True today. `parallelism.md`
      phase B is held; §4–§7 of that document describe a design, not code that
      exists. If the hold is ever lifted, this item needs revisiting rather than
      being read as a standing prohibition — the hold's own reopen conditions are
      in `parallelism.md` §13, and rescoping to four platforms has already
      satisfied one of them.)*
- [ ] No API keys or proxies are required.
- [ ] No existing coding assistant configuration is modified.
- [ ] Existing OpenCode and Cline functionality is preserved.
- [ ] Regression tests pass.

---

## 7. Mandatory Instructions for the Coding Agent

You are working inside an existing production-oriented codebase.

OpenCode and Cline CLI integrations are already completed.

Your task is to extend the existing application with Claude Code and Codex CLI support.

**Do not treat this as a greenfield project.**

Before making any code changes:

1. Inspect the existing repository.
2. Understand the existing OpenCode and Cline collectors.
3. Identify shared services and utilities.
4. Determine which existing functions can be reused.
5. Identify only the minimum necessary changes.
6. Produce a concise reuse assessment.

During implementation:

- Reuse existing code wherever compatible.
- Avoid unnecessary refactoring.
- Avoid duplicated services.
- Avoid new dependencies unless necessary.
- Keep Claude and Codex parsing platform-specific.
- Keep analytics and persistence shared.
- Preserve backward compatibility.
- Implement and test one platform at a time.
- Do not change existing user configurations.
- Do not collect API keys, prompts, or source code.

If an existing abstraction is insufficient, make the smallest backward-compatible extension that supports the new platform.

**Do not implement a second token tracker inside the existing token tracker.**

---

## 8. Final Goal

Extend the completed OpenCode + Cline CLI token tracker to support Claude Code and Codex CLI with native and compatible third-party models.

The implementation must use one shared architecture, one database, one processing pipeline, one backend, and one dashboard.

The primary development objective is:

**Maximum reuse + minimum new code + accurate token tracking + zero regression in existing integrations.**