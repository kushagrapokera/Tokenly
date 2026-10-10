# OpenCode Token Usage Tracker — Implementation Plan

## 1. Implementation Overview

Build a local-first application that automatically collects, stores, and visualizes token usage from OpenCode.

The application must work independently of the user's model provider, API key configuration, and model pricing.

**Core functionality:**

1. Track total input and output tokens.
2. Track daily, monthly, yearly, and all-time token consumption.
3. Track token usage separately for every model used through OpenCode.
4. Support free, paid, subscription-based, and locally hosted models.
5. Automatically import historical usage and monitor new usage.
6. Operate without requiring API keys, proxies, or modifications to OpenCode.

Only OpenCode will be implemented initially.

---

## 2. Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.10+ |
| Backend framework | FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy |
| Database migrations | Alembic |
| Frontend | React + TypeScript |
| Build tool | Vite |
| Styling | Tailwind CSS |
| Charts | Recharts |
| File monitoring | Watchdog |
| API communication | REST |
| Testing | Pytest, Vitest |
| Operating systems | Windows, Linux, macOS |

### Design Principles

- Local-first architecture
- Read-only access to OpenCode data
- Provider-independent token tracking
- Modular collector architecture
- Incremental synchronization
- Persistent historical data
- Accurate token normalization
- No duplicate counting
- Minimal setup
- Privacy by default

---

## 3. System Architecture

```text
                 OpenCode
                    |
                    v
          Local Session Storage
                    |
                    v
         OpenCode Data Discovery
                    |
                    v
           OpenCode Collector
                    |
                    v
          Usage Normalization
                    |
                    v
          Deduplication Engine
                    |
                    v
             SQLite Database
                    |
                    v
             FastAPI Backend
                    |
                    v
            React Dashboard
```

### Component Responsibilities

**OpenCode Data Discovery**

Finds the active OpenCode data directory and identifies the available session storage format.

**OpenCode Collector**

Reads session records and extracts usage information.

**Usage Normalization**

Converts OpenCode-specific usage fields into a common internal representation.

**Deduplication Engine**

Ensures that repeated scans, streaming updates, and session changes do not inflate token totals.

**SQLite Database**

Stores collected usage independently of OpenCode.

**FastAPI Backend**

Provides aggregated token statistics to the frontend.

**React Dashboard**

Displays token consumption over time and across models.

---

# Phase 1 — OpenCode Storage Investigation

## Objective

Determine exactly where and how OpenCode stores token usage.

This phase must be completed before implementing the production collector.

### Tasks

- [x] Identify the installed OpenCode version. → 1.18.35 (Linux)
- [x] Identify default data directories on Windows, Linux, and macOS. → Linux verified live; macOS/Windows resolved at runtime via `opencode db path` (see analysis §1)
- [x] Identify how custom data directories are configured. → `opencode debug paths` is the source of truth; no env var / config key set locally (see analysis §1)
- [x] Determine whether the installed version uses SQLite, JSON files, or another storage format. → SQLite (WAL) at `~/.local/share/opencode/opencode.db`, 19 tables (see analysis §2)
- [x] Identify session and message structures. → `session` + `message` (+`part`, `event`; `session_message`/`session_input` empty) (see analysis §3)
- [x] Locate token usage metadata. → `message.data.tokens` = authoritative; `session.tokens_*` = rollups (see analysis §4)
- [x] Locate provider identifiers. → assistant `message.data.providerID` (see analysis §5)
- [x] Locate model identifiers. → assistant `message.data.modelID` (+optional `variant`) (see analysis §5)
- [x] Locate message timestamps. → `data.time.created` (ms epoch UTC); `time.completed` marks end (see analysis §6)
- [x] Determine whether usage records represent individual model calls or cumulative totals. → one assistant message = one call; parts/session are cumulative-only (see analysis §7)
- [x] Investigate streaming usage updates. → `event` table streams; tokens settle on `time.completed` (see analysis §8)
- [x] Investigate session compaction and retry behavior. → `time_compacting` NULL locally; `message.removed.1` events observed; dedup key = `message.id` (see analysis §9)
- [x] Verify whether token counts are available for free models. → YES, 1588/1588 messages carry `tokens` (see analysis §10)
- [x] Verify whether token counts are available for third-party providers. → no live rows; schema-level handling documented, no allow-list (see analysis §11)
- [x] Determine how incomplete or interrupted requests are represented. → `finish` unknown/absent + `error` (MessageAbortedError) → zero-token events (see analysis §12)

### Useful OpenCode Commands

```bash
opencode --version
opencode stats
opencode session list
```

Check supported command options using:

```bash
opencode --help
opencode stats --help
opencode session --help
```

Do not assume the CLI statistics output contains every field required by the tracker.

### Deliverable

`docs/opencode_storage_analysis.md`

Document:

- Verified storage locations
- Supported storage formats
- Relevant data structures
- Token field definitions
- Model and provider identification
- Timestamp interpretation
- Known compatibility limitations
- Sanitized example records

### Completion Criteria

The collector's data source is verified using actual OpenCode records.

---

# Phase 2 — Backend Project Setup

## Objective

Create the backend foundation.

### Tasks

- [x] Initialize a Python project. → root `pyproject.toml` + `requirements.txt` + `requirements-dev.txt`
- [x] Configure a virtual environment. → `.venv/` (Python 3.14, git-ignored)
- [x] Install FastAPI and Uvicorn. → fastapi 0.143.0, uvicorn 0.54.0
- [x] Install SQLAlchemy and Alembic. → sqlalchemy 2.1.4, alembic 1.20.0
- [x] Configure SQLite. → `config/settings.py` (`data/tokenly.db`) + `database/connection.py`
- [x] Configure logging. → `logging_setup/configure.py`, one console handler, level from settings
- [x] Configure application settings. → `config/settings.py` (pydantic-settings, `.env` aware, `extra="ignore"`)
- [x] Create a collector interface. → `collectors/base.py` (`BaseCollector` ABC) + `schemas/usage.py`
- [x] Configure Pytest. → `tests/` + `[tool.pytest.ini_options]`; 11 tests green
- [x] Add type hints and code formatting. → mypy strict clean (22 files), ruff check + format clean
- [x] Add a health-check endpoint. → `GET /api/health` in `routes/health.py` (200 ok / 503 when DB unreachable)

### Proposed Directory Structure

```text
token-tracker/
|
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── collectors/
│   │   │   ├── base.py
│   │   │   └── opencode/
│   │   ├── services/
│   │   ├── database/
│   │   └── schemas/
│   ├── migrations/
│   ├── tests/
│   └── requirements.txt
|
├── frontend/
├── docs/
├── plan.md
├── implementation_plan.md
└── README.md
```

### Completion Criteria

The backend starts successfully and can connect to its SQLite database.

---

# Phase 3 — OpenCode Collector

## Objective

Build a read-only collector for OpenCode usage records.

### 3.1 Collector Interface

Create a common interface for future platform integrations.

```python
from abc import ABC, abstractmethod


class BaseCollector(ABC):
    @abstractmethod
    def discover(self):
        pass

    @abstractmethod
    def collect_history(self):
        pass

    @abstractmethod
    def collect_updates(self):
        pass
```

### 3.2 OpenCode Collector

```python
class OpenCodeCollector(BaseCollector):
    def discover(self):
        pass

    def collect_history(self):
        pass

    def collect_updates(self):
        pass
```

These are interface placeholders, not completed implementations.

### Tasks

- [x] Implement OpenCode data directory discovery. → `collectors/opencode/locator.py` (CLI-first, XDG/Windows fallback, logged)
- [x] Implement storage format detection. → `collectors/opencode/reader.py` (`verify_supported_schema`, `UnsupportedStorageFormatError`)
- [x] Implement session enumeration. → `collectors/opencode/reader.py` (`list_sessions`)
- [x] Implement message and usage extraction. → `collectors/opencode/extractor.py`
- [x] Extract provider IDs. → `data.providerID` (`require_text`)
- [x] Extract model IDs. → `data.modelID`; `variant` kept as metadata, not identity
- [x] Extract input tokens. → `tokens.input`
- [x] Extract output tokens. → `tokens.output`
- [x] Extract timestamps. → `data.time.created` (ms → UTC), column as fallback
- [x] Extract stable event identifiers. → `message.id` as `source_event_id`
- [x] Handle missing usage metadata. → `usage_status="unavailable"`, counts `None` (never 0)
- [x] Handle corrupted or incomplete records. → `json_valid` SQL guard + per-row skip + named errors
- [x] Support historical imports. → `collect_history()`
- [x] Support incremental collection. → `collect_updates()` + `collectors/checkpoint.py`

### Findings That Shaped the Implementation

Verified against the live database (OpenCode 1.18.35), beyond the Phase 1 document:

1. **`tokens.total` is not `input + output`.** 1,258 of 1,271 rows with a total matched
   `input + output + reasoning + cache.read`. Totals are therefore always computed from
   the two non-overlapping counts; the reported total is preserved in `raw_usage`.
2. **A message can be mid-generation.** One assistant message currently has no
   `time.completed`; it is deferred, and the checkpoint re-reads its millisecond so the
   finished record is picked up on the next scan.
3. **`APIError` exists alongside `MessageAbortedError`.** The Phase 1 doc listed only the
   latter; both are preserved in `raw_usage["error"]`.
4. **`json_extract` raises on malformed JSON.** A corrupt `data` column aborts the whole
   scan, so the reader guards with `json_valid(data)` first.
5. **`opencode debug paths` uses space-aligned columns**, not tabs. All three plausible
   formats are handled and tested.

### Important Requirements

The collector must:

- Never modify OpenCode's source data. → opened `mode=ro`, read through a SQLite online
  backup into a temp dir that is deleted afterwards; asserted byte-for-byte in tests
- Never read or store API keys. → only token/model/time/status fields are extracted
- Never require an API proxy. → pure local file reads
- Never depend on model pricing. → `cost` is never read
- Never assume all providers expose complete usage metadata. → no provider allow-list;
  any `providerID` is handled uniformly

### Completion Criteria

The collector successfully extracts normalized usage candidates from real OpenCode sessions.
→ **Verified**: 1,713 records from 27 live sessions, ids unique, totals equal
input + output on every row, and per-model sums reconcile with `opencode stats`
(8,868,237 input vs 8.9M; 482,162 output vs 482.5K). 22 learning tests in
`tests/collectors/opencode/test_learning_tests.py` pin the boundary shapes.

---

# Phase 4 — Token Normalization

## Objective

Convert OpenCode usage information into a consistent representation.

### Normalized Usage Schema

```json
{
  "platform": "opencode",
  "provider_id": "openrouter",
  "model_id": "example-model",
  "session_id": "session_123",
  "message_id": "message_456",
  "source_event_id": "event_789",
  "timestamp": "2026-10-10T12:00:00Z",
  "input_tokens": 12000,
  "output_tokens": 3000,
  "total_tokens": 15000,
  "usage_status": "reported"
}
```

This is an illustrative internal schema.

### Normalization Rules

1. [x] Preserve the original provider and model identifiers. → passed through untouched
2. [x] Normalize timestamps to UTC. → `normalize_timestamp`
3. [x] Use nonnegative integer token counts. → `read_count` rejects negatives, bools, floats
4. [x] Represent unavailable values as `null`. → `None` throughout; zero is kept as zero
5. [x] Distinguish reported usage from estimated usage. → `resolve_usage_status`
6. [x] Determine whether cached tokens overlap with input tokens. → **additive**, see below
7. [x] Determine whether reasoning tokens overlap with output tokens. → **additive**, see below
8. [x] Prevent overlapping categories from being counted twice. → `sum_every_category`
9. [x] Preserve raw token metadata where useful for future compatibility. → `raw_usage`

### Overlap Finding (rules 6, 7, 8)

Measured against 1,748 live OpenCode messages, the identity

```text
total == input + output + reasoning + cache.read + cache.write
```

held on **1,415 of 1,415** records that carried a total. Were cache a subset of input,
OpenCode would not have added it again — so on OpenCode both categories are **additive**,
not overlapping.

Consequence: `total_tokens = input + output` (9.39M) is the per-call figure, while
`consumption_tokens` adds reasoning and cache (138.2M). Reporting only the former would
undercount real consumption roughly 14x. `consumption_tokens` independently reproduces
OpenCode's own reported total on 1,435 of 1,435 records.

The relationship is data, not an assumption: it lives in `normalization/categories.py`
as `CategoryRelationships`, so a future provider with different semantics declares its
own instead of inheriting OpenCode's. `tests/test_normalization_learning.py` fails if
the relationship stops holding against real data.

### Total Token Calculation

For records where input and output are complete and non-overlapping:

```text
total_tokens = input_tokens + output_tokens
```

If the source reports other categories separately, first establish their relationship to
input and output. → established above as additive, so secondary categories are excluded
from `total_tokens` and reported through `consumption_tokens`.

Do not invent missing token values. → a total is emitted only when every category it
sums is known; a partial sum is reported as unknown, never as a smaller number.

### Completion Criteria

All supported OpenCode usage records are converted into a consistent schema without token
double counting. → **Verified**: 1,795 live records, every `total_tokens` equal to its
input + output, every `consumption_tokens` equal to the sum of all five categories, and
per-category totals reconcile with `opencode stats` (input 8,884,730 vs 8.9M; output
506,344 vs 506.3K; cache read 128,423,097 vs 128.4M). 37 normalization tests, 10 of them
learning tests against real data.

---

# Phase 5 — Database Design

## Objective

Persist normalized usage and synchronization state.

### Table: usage_events

| Column | Type | Purpose |
|---|---|---|
| id | INTEGER | Primary key |
| platform | TEXT | OpenCode |
| provider_id | TEXT | Model provider |
| model_id | TEXT | Model identifier |
| session_id | TEXT | Source session |
| message_id | TEXT | Source message |
| source_event_id | TEXT | Stable usage event ID |
| timestamp | DATETIME | Usage timestamp |
| input_tokens | INTEGER NULL | Input token count |
| output_tokens | INTEGER NULL | Output token count |
| total_tokens | INTEGER NULL | Combined tokens |
| usage_status | TEXT | Reported, estimated, unavailable |
| raw_usage | JSON/TEXT | Original usage metadata |
| created_at | DATETIME | Import timestamp |
| updated_at | DATETIME | Last update timestamp |

### Table: collector_state

| Column | Type |
|---|---|
| id | INTEGER |
| platform | TEXT |
| source_path | TEXT |
| checkpoint | TEXT |
| last_scan_at | DATETIME |
| status | TEXT |

### Database Requirements

- [x] Unique constraints for stable source event IDs.
      → `UNIQUE (platform, source_event_id)`; `message.id` is the stable key
- [x] Indexes on timestamps. → `ix_usage_events_timestamp`, `ix_usage_events_platform_timestamp`
- [x] Indexes on provider and model identifiers. → `ix_usage_events_provider_id`, `ix_usage_events_model_id`
- [x] Support upsert operations. → `upsert_usage_records` via SQLite `ON CONFLICT DO UPDATE`
- [x] Support schema migrations. → `alembic/versions/0001_initial_create_usage_tables.py`, verified up/down with zero drift
- [x] Preserve usage when original session files are deleted. → no delete path exists; rows are independent of OpenCode's storage
- [x] Support efficient date-range aggregation. → verified with `EXPLAIN QUERY PLAN`: all five query shapes use an index

### Schema Notes

Two columns beyond the table above were added for Phase 4's findings, since
`total_tokens` alone cannot carry the additive categories:

| Column | Purpose |
|---|---|
| `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens` | the additive categories, queryable instead of buried in JSON |
| `consumption_tokens` | true total: input + output + reasoning + cache |

Two `CHECK` constraints guard the data the normalizer promises: token counts must be
nonnegative, and `usage_status` must be one of the three known values. A row violating
either is rejected by the database rather than trusted.

### Implementation

| File | Concern |
|---|---|
| `database/types.py` | `UtcDateTime` — SQLite returns naive datetimes, so values are pinned to UTC on write and re-tagged on read |
| `database/models.py` | ORM models, constraints, indexes |
| `database/repository.py` | idempotent upsert, filtered queries, token sums |
| `database/state.py` | per-platform checkpoint storage |

`created_at` is excluded from the update set, so re-importing a record refreshes the
usage without moving the original import time. `mark_scanning` and `mark_error` change
only the status: a failed scan must not clear the checkpoint, or the retry would skip the
window it never finished.

### Completion Criteria

Usage records can be stored, queried, and updated without duplicates.
→ **Verified**: importing 1,871 live records twice produced 1,871 rows and an unchanged
total; a subsequent re-sync matched the collector exactly on every column. Five
re-imports of one record leave one row. 34 database tests.

---

# Phase 6 — Deduplication and Incremental Sync

## Objective

Prevent incorrect totals and support automatic updates.

### Deduplication Requirements

- [x] Identify usage events using stable source identifiers.
      → `source_event_id` = OpenCode `message.id`, unique per platform
- [x] Avoid counting the same message repeatedly.
      → `UNIQUE (platform, source_event_id)` plus upsert; 10 repeat runs add nothing
- [x] Handle updates to existing usage records.
      → upsert refreshes counts, never `created_at`
- [x] Handle streaming partial usage.
      → a message with no `time.completed` is reported as pending and holds the checkpoint
- [x] Handle retries. → a re-sent message updates its row; verified in `test_a_retried_message_updates_its_row_instead_of_adding_one`
- [x] Handle session compaction. → no delete path exists; stored usage survives an emptied source
- [x] Distinguish individual usage events from cumulative counters.
      → tokens come from `message.data`, never from `part` step-finish rollups or `session` columns

### Tasks

- [x] Implement initial historical scan. → no stored checkpoint reads everything
- [x] Implement incremental scanning. → resumes from the stored checkpoint
- [x] Implement event upserts. → reuses Phase 5 `upsert_usage_records`
- [x] Implement synchronization checkpoints. → `database/state.py`, advanced only after a successful store
- [x] Implement recovery after interrupted scans. → status `scanning`/`error` detected on restart; failed scan leaves the checkpoint untouched
- [x] Implement reconciliation after application restart. → fresh service re-reads from the checkpoint; upsert absorbs the overlap
- [ ] Implement filesystem monitoring where appropriate. → deferred; OpenCode is already running as this process, so a poll-on-demand model is simpler and sufficient
- [x] Add periodic rescan fallback. → `rescan_overlap_ms` pulls the resume point back, re-reading a recent window

### The Three Guards

Correctness here rests on three rules, each enforced in code:

1. **Checkpoint advances only after records are committed.** A crash in between leaves a
   stale checkpoint, which causes harmless re-reads; advancing first would skip usage
   permanently.
2. **An in-flight message holds the checkpoint back.** OpenCode writes a message when
   generation starts and fills in tokens when it finishes, so the checkpoint is capped at
   the oldest unfinished message.
3. **Nothing is deleted.** Compaction and retries remove source rows; usage stays.

### Implementation

| File | Concern |
|---|---|
| `collectors/base.py` | `ScanOutcome` — records plus the timestamps of messages still generating |
| `collectors/opencode/collector.py` | `collect_scan` reports in-flight messages |
| `sync/service.py` | orchestration, checkpoint arithmetic, failure handling |
| `sync/result.py` | what a run did |

### Completion Criteria

Repeated scans and application restarts do not inflate usage totals.
→ **Verified**: five consecutive runs against the live database produced identical
`(row count, total)` every time — `(1915, 158,041,747)` — and a simulated full restart
added nothing. Earlier runs did grow, traced to genuinely new usage from the running
OpenCode session, not duplication. 35 sync tests.

---

# Phase 7 — Usage Aggregation

## Objective

Calculate time-based and model-wise token consumption.

### Supported Aggregations

- Today
- Yesterday
- Last 7 days
- Current month
- Previous month
- Current year
- All time
- Custom date range

### Example SQL

```sql
SELECT
    provider_id,
    model_id,
    SUM(input_tokens) AS input_tokens,
    SUM(output_tokens) AS output_tokens,
    SUM(total_tokens) AS total_tokens
FROM usage_events
WHERE timestamp >= :start_time
  AND timestamp < :end_time
GROUP BY provider_id, model_id;
```

### Important Rules

- Use the user's selected timezone for calendar boundaries.
- Store timestamps in UTC.
- Use half-open time intervals.
- Exclude unavailable totals from numerical sums.
- Report incomplete coverage separately.
- Keep providers distinguishable even when model names match.

### Completion Criteria

Daily, monthly, yearly, and model-wise totals are accurate and consistent.

---

# Phase 8 — FastAPI Endpoints

## Objective

Expose usage data to the dashboard.

### Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Application health |
| GET | `/api/usage/summary` | Overall usage |
| GET | `/api/usage/daily` | Daily totals |
| GET | `/api/usage/monthly` | Monthly totals |
| GET | `/api/usage/yearly` | Yearly totals |
| GET | `/api/usage/models` | Model-wise usage |
| GET | `/api/usage/timeline` | Usage over time |
| GET | `/api/collector/status` | Collector health |
| POST | `/api/collector/rescan` | Trigger historical rescan |

### API Requirements

- Validate date-range parameters.
- Support provider and model filtering.
- Return consistent JSON responses.
- Include data completeness indicators.
- Handle empty results.
- Handle collection errors.
- Bind the local API to loopback by default.
- Restrict cross-origin access to the local frontend.

### Completion Criteria

All dashboard data can be retrieved through tested API endpoints.

---

# Phase 9 — Frontend Dashboard

## Objective

Create a responsive interface for OpenCode usage analytics.

### 9.1 Frontend Setup

- [ ] Initialize React + TypeScript using Vite.
- [ ] Configure Tailwind CSS.
- [ ] Configure Recharts.
- [ ] Configure API client.
- [ ] Add loading and error states.

### 9.2 Dashboard Metrics

Display:

1. Tokens today
2. Tokens this month
3. Tokens this year
4. All-time tokens

### 9.3 Model Breakdown

Display:

- Model name
- Provider
- Input tokens
- Output tokens
- Total tokens
- Request count

### 9.4 Charts

Implement:

- Daily token usage line chart
- Monthly usage bar chart
- Yearly usage chart
- Model usage comparison
- Input/output token breakdown

### 9.5 Filters

Support:

- Date range
- Provider
- Model

### 9.6 Tracking Status

Display:

- OpenCode detection status
- Last successful synchronization
- Imported usage event count
- Collection errors
- Incomplete usage warnings

### Completion Criteria

The dashboard accurately displays data returned by the backend.

---

# Phase 10 — Testing and Validation

## Objective

Validate correctness across different OpenCode usage scenarios.

### Unit Tests

- [ ] Token normalization.
- [ ] Total token calculation.
- [ ] Timestamp conversion.
- [ ] Model identification.
- [ ] Provider identification.
- [ ] Deduplication.
- [ ] Aggregation.
- [ ] Missing usage handling.

### Integration Tests

- [ ] Single session with one model.
- [ ] Multiple sessions with one model.
- [ ] Multiple models in one session.
- [ ] Multiple providers.
- [ ] Free hosted model.
- [ ] Paid API model.
- [ ] Local model.
- [ ] Interrupted requests.
- [ ] Streaming updates.
- [ ] Retried requests.
- [ ] Session compaction.
- [ ] Historical import.
- [ ] Application restart.
- [ ] Deleted original session history.

### Validation

Compare collected token usage with OpenCode's own reported statistics wherever possible.

Document any discrepancies.

### Completion Criteria

Critical tests pass, and known data limitations are documented.

---

# Phase 11 — Packaging and Local Deployment

## Objective

Make the application easy to install and run.

### Tasks

- [ ] Package the backend.
- [ ] Build the frontend.
- [ ] Configure local database initialization.
- [ ] Configure automatic OpenCode discovery.
- [ ] Provide a simple startup command.
- [ ] Provide Windows installation instructions.
- [ ] Provide Linux installation instructions.
- [ ] Provide macOS installation instructions.
- [ ] Handle missing OpenCode installations gracefully.
- [ ] Provide application logs for troubleshooting.

### Completion Criteria

A user can launch the tracker locally without modifying their OpenCode configuration.

---

## 12. Development Milestones

| Milestone | Deliverable |
|---|---|
| M1 | Verified OpenCode storage analysis |
| M2 | Working historical usage collector |
| M3 | Normalized SQLite storage |
| M4 | Accurate deduplication and synchronization |
| M5 | Daily, monthly, yearly, and model-wise aggregation |
| M6 | Functional FastAPI backend |
| M7 | Functional React dashboard |
| M8 | Automated collection and validation |
| M9 | Locally deployable MVP |

---

## 13. MVP Acceptance Criteria

The implementation is complete when:

- [ ] OpenCode is automatically detected.
- [ ] Historical usage is imported where available.
- [ ] New usage is collected automatically.
- [ ] Input and output tokens are tracked.
- [ ] Total token consumption is calculated accurately.
- [ ] Daily usage is available.
- [ ] Monthly usage is available.
- [ ] Yearly usage is available.
- [ ] Model-wise usage is available.
- [ ] Multiple providers are supported.
- [ ] Free and paid models are supported where usage metadata exists.
- [ ] Duplicate counting is prevented.
- [ ] The dashboard updates with new usage.
- [ ] No API keys are required.
- [ ] OpenCode configuration remains unchanged.
- [ ] Collected history survives source record deletion.
- [ ] Missing or incomplete usage is reported accurately.

---

## 14. Future Compatibility

Although only OpenCode is implemented initially, the codebase must allow additional platform collectors later.

Potential future integrations:

- Codex CLI
- Claude Code
- Cline CLI
- Antigravity
- FreeBuff

Future capabilities may include:

- Cache hit/miss analytics
- Cache read/write tokens
- Token cost estimation
- Quota monitoring
- Multi-platform usage comparison
- Cloud synchronization

These features must not delay or expand the initial OpenCode MVP.

---

## 15. Final Implementation Goal

Deliver a fully functional, local-first OpenCode Token Usage Tracker that automatically collects available token usage information and displays accurate daily, monthly, yearly, and model-wise statistics.

The application must remain independent of model providers, API keys, and pricing.

**The first development task is to verify OpenCode's local storage format and identify the authoritative token usage records. Do not begin implementing the full collector until this is confirmed.**