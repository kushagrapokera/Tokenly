# Parallelism.md — making collection fast, and keeping it fast as platforms are added

**Status:** A0–A3 are implemented and measured (see §1 and §13). All of phase B
is still plan, and is gated on re-measuring first.

**Scope:** how collection and storage of usage records gets faster today, and how
the same design keeps working when Claude, Codex, Antigravity and others are
added. Every number below was measured on this machine against the real OpenCode
and Cline stores; anything projected is labelled as such.

**Context:** Tokenly runs locally on one machine for one user — never hosted,
never shared. Several decisions below are only sound because of that, so those
assumptions are written down explicitly in §10 rather than left implicit.

---

## 1. What is actually slow (measured)

Median of 5 runs, warm page cache, 4,700 stored records (2,603 OpenCode + 2,142 Cline).

A0 has since removed the subprocess from the scan path. The "before" column is
what the plan was written against; "now" is measured after A0.

| Stage | Before | Now | Note |
|---|---:|---:|---|
| **OpenCode `collect_history()`** | **836 ms** | **276 ms** | |
| ↳ `opencode debug paths` subprocess | ~597 ms | **0 ms** | paid once per collector, not per scan |
| ↳ snapshot copy of the live database | ~172 ms | **0 ms** when unchanged | A2 reuses the copy; still copied when the source changes |
| ↳ indexed SQL query | 11 ms | 11 ms | `message_session_time_created_id_idx` already exists |
| ↳ row decode + model construction | ~40 ms | ~40 ms | *variable* — the only part batching could touch |
| ↳ `json.loads` | ~11 ms | ~11 ms | 29 sessions, median 0.1 ms each |
| **Cline `collect_history()`** | **144 ms** | **144 ms** | untouched by A0 |
| ↳ read + `json.loads` of 42 session files | ~100 ms | ~100 ms | *variable* — 42 independent files |
| ↳ normalize in Python | ~33 ms | ~33 ms | |
| **Sequential total** | **948 ms** | **~420 ms** | |
| Write: first import, 2,142 rows | 174 ms | **~40 ms** | one batched transaction (A1) |
| Write: re-import, 2,142 existing rows | **1,125 ms** | **71 ms** | one `UPDATE` per row → one batched upsert (A1) |
| Dashboard `summary` / `breakdown` | 1.3 / 2.4 ms | 1.3 / 2.4 ms | |
| Dashboard `timeline` (daily, 365 buckets) | 43 ms | **8.2 ms** | A3 replaced a linear edge scan with a binary search |

**Fixed versus variable — the distinction the whole plan turns on** (before A0):

| Platform | Fixed per scan | Variable per scan | What that means |
|---|---:|---:|---|
| OpenCode | ~769 ms (subprocess + snapshot) | ~51 ms | Batching can only touch the 51 ms |
| Cline | ~0 ms | ~144 ms | Batching is the only lever here |

OpenCode's cost is almost entirely *fixed*: one subprocess and one database copy,
per scan, regardless of how many records exist. A0 and A2 delete that fixed cost
outright. Spreading ~51 ms of variable work across four workers would save about
8 ms. **Batching OpenCode is not worth doing, and phase B should skip it** — see
§13 and the note in B5.

Three things follow, and they reframe the whole problem:

1. **Token arithmetic is not the bottleneck.** Summing tokens is 1.3 ms, because
   SQLite does it in one indexed query. The per-record token math is ~130 ms of
   948 ms. Collection is I/O and JSON parsing, not arithmetic.
2. **The single largest cost in the entire pipeline is a subprocess that answers
   a question about a file path.** ~597 ms, every scan, for data that changes
   once per install.
3. **The second largest is a write loop that could be one statement.** 1,125 ms
   to re-import rows that already exist.

Neither is a parallelism problem. Parallelism is worth doing, but it is phase B,
and it should not be reached for before phase A.

---

## 2. Does parallelism actually help? (measured)

| Strategy | Before | After | Change |
|---|---:|---:|---:|
| Two collectors in **threads** | 948 ms | 839 ms | −11% |
| Two collectors in **processes** | 948 ms | 842 ms | −11% |
| Cline's 42 files across **4 threads** | 124 ms | 134 ms | **worse** |
| Cline's 42 files across **4 processes** | 124 ms | 85 ms | −31% |
| OpenCode's 29 sessions across 4 processes | ~51 ms variable | ~13 ms | −38% of 4% of the scan |

Three consequences shape the design:

- **Parallelising across platforms buys ~11% today.** OpenCode dominates, so
  Amdahl caps the win at whatever the smaller collector costs. It is not worth
  machinery on its own.
- **Threads do not work.** `json.loads` and model construction hold the GIL; four
  threads measuring *slower* than one is the expected result, and it was
  observed. Only processes help. (One exception noted in §8.)
- **The parallelism that pays is inside Cline**, whose 42 session files are
  genuinely independent and carry ~144 ms of variable work. OpenCode's 29
  indexed sessions are technically batchable too, but at 0.1 ms of parsing each
  they are not worth it — see §4.3.

---

## 3. The core design decision: parallelise *batches*, not *platforms*

The obvious design — "run the collectors in parallel" — is the wrong unit. It
caps out at −11% today, and with more platforms it still leaves a straggler
holding the whole pass back, because every platform's work is one indivisible job.

Instead, **every collector publishes a flat list of independent batches, and all
batches from all platforms go into one queue.** Workers drain that queue.

```
                    ┌──────────────────────────────────────────┐
                    │  collector.iter_batches()  (per platform) │
                    └──────────────────────────────────────────┘
                                      │
   opencode: [s1] [s2] [s3] … [s29]      │      cline: [f1] [f2] … [f42]
                                      ▼
                    ┌──────────────────────────────────────────┐
                    │   one work queue, sorted longest-first   │
                    └──────────────────────────────────────────┘
                          │            │            │
                       worker 1     worker 2     worker 3      (processes)
                          │            │            │
                          └────────────┴────────────┘
                                       ▼
                        merge → one transaction per platform → checkpoint
```

Why this is the right unit:

- **It is platform-count-agnostic.** Adding Claude adds batches to the same queue.
  No coordinator change, no scheduler change, no new concurrency code.
- **It self-balances.** A platform with 3 units does not hold up a platform with
  400. Longest-batch-first ordering keeps the tail short.
- **It degrades honestly.** One platform with one batch simply gets no
  parallelism, because there is nothing to spread. The system does the right
  thing without being told.
- **Threads/processes is an implementation detail.** The queue is the contract.

Projected makespan for N platforms of roughly equal size (≈150 ms each, 4 workers):

| Platforms | Sequential today | Batch queue (projected) |
|---:|---:|---:|
| 2 | ~300 ms | ~150 ms |
| 5 | ~750 ms | ~250 ms |
| 10 | ~1,500 ms | ~450 ms |

These are projections from the measured −31% per-unit scaling, not measurements.
Step B6 exists to measure them.

---

## 4. Contracts

### 4.1 One new dataclass, in the module that already owns the collector interface

```python
# collectors/base.py — new, alongside ScanOutcome

@dataclass(frozen=True)
class CollectorBatch:
    """One independently scannable unit of a platform's history.

    `key` identifies the unit to a worker (a session id, a file name). `collect`
    is the only thing a worker calls; it must touch nothing outside its unit.
    """
    key: str
    collect: Callable[[], list[UsageRecord]]
```

`ScanOutcome` is reused unchanged as the merged result of a platform's scan, so
no new result type is introduced.

### 4.2 One new method on `BaseCollector`, with a working default

```python
# collectors/base.py

def iter_batches(self, checkpoint: str | None = None) -> list[CollectorBatch]:
    """Split this platform's work into independent units.

    The default keeps every existing collector working exactly as it does today:
    one batch holding the whole history. A collector overrides this to be
    parallelised. No subclass is forced to implement anything.
    """
    return [CollectorBatch(key=self.platform, collect=lambda: self.collect_updates(checkpoint))]
```

This is the compatibility hinge. OpenCode and Cline keep working with **zero
changes** on day one; each opts in later by overriding one method. As measured,
**Cline is the only platform expected to override it** — see §4.3.

### 4.3 Overriding it — Cline only, for now

```python
# collectors/cline/collector.py — 42 independent files become 42 batches
def iter_batches(self, checkpoint=None) -> list[CollectorBatch]:
    return [
        CollectorBatch(key=session_id, collect=partial(self._batch, session_id))
        for session_id in self._session_ids()
    ]
```

**OpenCode does not override this.** Its sessions are 0.1 ms of parsing each
(§1), so sharding them would save roughly 8 ms while costing pool overhead. It
keeps the default single-batch implementation and is scanned sequentially.

This matters more than it looks, because batching OpenCode would be actively
harmful. `collect_scan` and `_iter_records` each take their own snapshot
(`collectors/opencode/collector.py:128` and `:155`), so 29 batches would mean 29
full copies of the live database — about 5 seconds. Two ways avoid that, and
neither is needed once OpenCode stays unbatched:

1. **Share one snapshot across batches.** Workers open their own `mode=ro`
   connection to a snapshot the parent already took. Verified safe: 8 processes
   reading one read-only snapshot concurrently returned identical results.
2. **Land A2 first**, so the snapshot cache makes repeated copies nearly free.

Both are **deferred, not rejected.** They exist only to shard a *single-file
SQLite source*, and no current platform needs that: Cline's 42 units are separate
files, each read on its own. If a future platform has one large database worth
sharding, and measurement shows sharding it helps, revisit these — and expect to
need both.

---

## 5. Execution flow

The coordinator gains a batching path; `SyncService` keeps owning the scan, and
every part of it that already works is reused untouched.

```python
# sync/coordinator.py — replaced body of _run_one
batches = collector.iter_batches(resume_from)
records = executor.drain(batches)                 # parallel, processes
outcome = ScanOutcome(records=records, pending_timestamps_ms=[])
return build_sync_service(collector, settings).run(session, outcome=outcome)
```

```python
# sync/service.py — the ONLY change to this file: one optional keyword.
# When `outcome` is supplied the collector is not called again; the checkpoint,
# overlap, upsert, and error-recording logic below it is completely unchanged.
def run(self, session, *, from_scratch=False, outcome: ScanOutcome | None = None) -> SyncResult:
```

Everything already written stays:

| Existing component | Reused for |
|---|---|
| `SyncService` | scan ownership, error recording, result shape |
| `Checkpoint` | resume points and `covers()` semantics — unchanged |
| `_resume_point` | the rescan overlap window — unchanged |
| `upsert_usage_records` | the single write transaction — unchanged |
| `save_progress` / `mark_error` / `mark_scanning` | checkpoint and status — unchanged |
| `ScanOutcome` | the merged result type — unchanged |
| `snapshot_database` | the read-only copy — unchanged |

---

## 6. Correctness: the part that must not be got wrong

Parallel collection creates a failure mode that does not exist today — a
*partial* scan. Three rules follow from the existing design:

**6.1 One writer.** SQLite permits exactly one writer per database. Collection is
parallel; **writing is not.** All of a platform's batches are merged and written
in a single transaction by the existing `upsert_usage_records`. Verified safe:
concurrent readers are fine, concurrent writers would not be.

**6.2 The checkpoint must never run ahead of what was collected.** The checkpoint
means "everything older than this has been stored". If batch *B* fails, messages
in *B*'s range are missing, so the checkpoint must stay below the earliest
message *B* could have contained:

```
all batches ok   → checkpoint = max(timestamp of everything collected)
some batch failed → checkpoint = min(earliest timestamp of each failed batch) − 1
```

**Never** advance to the global maximum when a batch failed — that silently skips
usage forever, which is the exact failure mode `SyncService`'s own docstring
warns about. This rule is new logic and needs its own tests.

**6.3 Order does not matter, and that is already true.** Records are deduplicated
by `(platform, source_event_id)` and the checkpoint is a `max(timestamp)`, so
batches may complete in any order without changing what gets stored. This
invariance is what makes parallelism safe; it is pinned by existing tests and
must keep passing.

**6.4 Pending messages must be gathered per batch, not per scan.** Cline's
`collect_scan` always returns `pending_timestamps_ms=[]`, because its messages
arrive complete. OpenCode's does not: it appends the timestamp of every message
still generating (`collectors/opencode/collector.py:134`), and `SyncService`
holds the checkpoint back for exactly those. A batched scan must collect that
list **per batch and merge it**, or §6.2 will advance past a message whose usage
has not landed. The merged `ScanOutcome` already carries a flat list, so the
merge is trivial — but it has to be done deliberately, because OpenCode is the
platform that is *not* batched and a Cline-only implementation would look
correct until OpenCode is ever switched on.

**6.5 Idempotence absorbs the rest.** Re-running is safe because the upsert
updates in place. A worker that dies mid-scan costs re-read time, never double
counting.

---

## 7. Process pool lifecycle

A pool is created **once** at application startup and reused. Forking
interpreters per scan (every 300 s) would discard the gains.

| Concern | Decision |
|---|---|
| Pool | `ProcessPoolExecutor`, created in the FastAPI lifespan, shut down on exit |
| Sizing | `min(4, cpu_count − 1)`, overridable by setting. 4 because Cline's total parse work is ~100 ms — more workers only add overhead — and because the machine belongs to the user, who may well be compiling something else at the same time |
| Start method | `fork` where available (cheap, copy-on-write); otherwise default |
| Fallback | if the pool cannot start (restricted environment, unusual platform), log once and run batches sequentially. Parallelism is an optimisation, never a requirement |
| Memory | each worker allocates only its own batch. `fork` shares the parent's pages copy-on-write; the whole record set is a few MB |
| Sleep | the interval waits on `asyncio.wait_for`, which uses the event loop's **monotonic** clock. On a laptop that suspends, wall-clock time jumps; a monotonic timer is unaffected, so no catch-up burst and no double scan on resume. Do not "simplify" this to `time.time()` |

---

## 8. Why processes, and the one exception

The GIL makes threads useless for the dominant work:

- `json.loads` holds the GIL → Cline with 4 threads was **slower** than 1 (124 → 134 ms).
- Model construction and dataclass work hold the GIL.
- **Exception:** the `opencode debug paths` subprocess (~597 ms) is spent waiting
  on another process, which releases the GIL. If phase A's caching is ever
  declined, threads would parallelise *that* well. Caching it is still the better
  fix — see A0.

**IPC format:** measured, not currently a problem. Pickling 2,142 `UsageRecord`
objects costs 25 ms round trip — 2.7% of collection. Plain tuples are 2.2×
cheaper (11.7 ms) but then the parent must rebuild every model, which moves the
cost rather than removing it. **Ship the records as they are**; revisit at B6
when there are enough platforms for it to matter. Building a serialisation layer
now would be complexity with no measured payoff.

---

## 9. Hardware sizing (this machine)

This runs locally on one machine, for one user. Nothing here is sized for
serving anyone else.

| Spec | Consequence |
|---|---|
| 8 cores | Parallelism is affordable. 4 workers is the sweet spot: more only adds overhead for ~100 ms of parse work. The reason to stop at 4 is **courtesy** — the machine belongs to the user, who may be compiling or testing at the same time — not headroom for traffic. |
| 16 GB RAM, ~6 GB free | Not a constraint. `fork` is copy-on-write; the entire record set is a few MB. To be confirmed by measuring peak RSS in B5. |
| RTX 3050 | **No role, by design.** This workload is `json.loads` and SQLite — CPU and I/O. Nothing here is GPU-shaped, and no CUDA/ML dependency will be introduced. Local-only settles it further: there is nothing to serve a model to. |
| Disk | The 172 ms snapshot and the file reads are the I/O-bound part. An SSD matters more here than any core count. |
| Battery | A scan costs well under a second per cycle, so background collection is not a meaningful drain. The reason to make scans cheap is §15, not power. |

---

## 10. Assumptions this design relies on

Tokenly runs **locally, on one machine, for one user**. That is a design
constraint, not a deployment detail, and several decisions below only hold
because of it. If the project is ever hosted or shared, these are the
assumptions that break first — and they should break the design deliberately,
not silently.

| Assumption | What it buys | What breaks without it |
|---|---|---|
| One user, one machine | Process-lifetime caches (A0) never need cross-user invalidation; worker count is sized for courtesy, not load | A shared instance would need per-user path caches and a real scheduling policy |
| Long-lived local process | A cache that lives as long as the process is equivalent to a persistent one, so no cache file is needed | A serverless or frequently-restarted host would pay the probe on every cold start, making a persisted cache worthwhile |
| Only this user reads the dashboard | Nothing is ever waiting on a 1.3 s import; scans run in the background, which is why cost-per-scan (§15) matters more than latency | Remote clients would make scan latency user-visible |
| SQLite single writer | Collection is parallel, writing is not, with one transaction per platform | A networked database would allow concurrent writers and change §6.1 |
| No shared cache | A resolved path belongs to this machine and this install; the only invalidation is the user moving their own config | A multi-tenant deployment would need a different resolution strategy entirely |
| The machine suspends | Intervals use the monotonic event-loop clock, so sleep/resume causes no catch-up burst | Not applicable |

**What does not depend on any of this:** the collector contract (§4), the
single-writer barrier (§6.1), and the checkpoint rule (§6.2). Those hold under
any deployment, which is why they are the parts worth testing hardest.

---

## 11. New platforms: the checklist this design has to satisfy

Adding a provider must require **only** the collector contract. Nothing in
`sync/` or `main.py` may change. Concretely, a new Claude or Codex collector needs:

1. `platform`, `discover()`, `collect_history()`, `collect_updates()` — as today.
2. Optionally override `iter_batches()` to be parallelised. **Optional.** A
   collector that does not override it still works, just as one batch. Cline is
   the only current platform that overrides it; a new one inherits a working
   sequential path for free.
3. Register it in `collectors/registry.py`. One line.

It must **not** need to know about: workers, queues, snapshots, checkpoints,
transactions, or the coordinator. Those stay behind the contracts in §4.

The test that enforces this is a *conformance suite* (B6): a fake third platform
written against the public contract alone, run through the real scheduler, must
collect correctly with no changes to `sync/`. If adding a platform ever requires
editing the executor, this design has leaked and should be corrected.

---

## 12. Files

### New (2, both small)

| File | Why it is genuinely new |
|---|---|
| `sync/executor.py` | Concurrency is a new concern. Folding it into `sync/service.py` would give that file two jobs, against the project's one-concern-per-file rule. |
| `scripts/benchmark_sync.py` | Measurement, following the existing `scripts/validate_against_opencode.py` pattern. |

### Modified (additive only — no behaviour changes by default)

| File | Change | Risk |
|---|---|---|
| `collectors/base.py` | + `CollectorBatch`, + `iter_batches()` **with a default** | None — existing collectors unaffected |
| `sync/service.py` | + one optional `outcome=` keyword | Low — existing call sites unchanged |
| `sync/coordinator.py` | batching path instead of one call per collector | Medium — covered by existing coordinator tests |
| `main.py` | create/shutdown the pool in the lifespan | Low |
| `config/settings.py` | `sync_max_workers`, `sync_parallel: bool` | None |
| `collectors/cline/collector.py` | override `iter_batches()` (opt-in) | Medium — must equal today's output |

No file is deleted, renamed, or restructured. No new dependency is added.
**`collectors/opencode/` is not touched at all** — it keeps the default
single-batch implementation (§4.3).

---

## 13. Rollout

Each phase is independently shippable and independently measurable. Stop after
any of them.

### Phase A — the bottlenecks (no architecture change)

| # | Change | Expected | Risk |
|---|---|---|---|
| **A0** | ~~Cache the resolved OpenCode data directory instead of re-running `opencode debug paths` per scan~~ | **done — 836 → 276 ms** | See the rules below |
| A1 | ~~Replace the per-row `UPDATE` loop with one bulk `INSERT … ON CONFLICT DO UPDATE`~~ | **done — 1,125 → 71 ms** | `UpsertResult` counts preserved; old SQLite keeps a correct row-at-a-time path |
| A2 | ~~Skip the snapshot when the live DB is unchanged~~ | **done — status view 194 → 7 ms** | Fingerprint must include the write-ahead log, or new usage is missed |
| A3 | ~~Timeline: find each row's bucket without a linear scan~~ | **done — 43 → 8.2 ms** | Must return identical buckets, especially across DST |

#### A1 — what it does, and the SQLite question

The whole batch now goes out as one `INSERT … ON CONFLICT DO UPDATE`, with
`excluded` supplying the updated values so the same statement covers both an insert
and a refresh. SQLAlchemy splits it into `executemany` batches internally, so a
re-import of 2,142 records is one logical statement instead of 2,142 of them.

*Answering §17's question:* `ON CONFLICT DO UPDATE` needs SQLite ≥ 3.24 (2018).
Everything Python 3.10+ ships with satisfies it — this machine has 3.53.2 — but a
locally built interpreter can be linked against an older library, so the batched
write is guarded by a version check and the row-at-a-time path remains as a
correct fallback. It is tested for identical behaviour, not merely present.

`UpsertResult` still reports what it did. The inserted/updated split comes from
the same single indexed SELECT that already existed; one cheap query costs far
less than the write it precedes.

#### A2 — reusing the copy, and the trap in it

Implemented as `SnapshotCache`. A copy is reused while the source looks exactly as
it did when it was taken. Measured on the live store: `/api/collector/status`
went from 194 ms to **7 ms**, with a cache hit on every one of five scans spaced
1.5 s apart while idle.

**The trap:** OpenCode runs in WAL mode, so new messages are committed to
`opencode.db-wal` and can leave the main file's size and modification time
completely unchanged. Fingerprinting the main file alone — the obvious
implementation — reuses a copy that is missing the very usage it was asked to
find. The fingerprint therefore covers the write-ahead log as well, while
excluding `-shm`, whose timestamp moves without any data changing. Verified on
this machine: the `-wal` file really is present.

If the fingerprint ever lies, the failure is bounded. The reused copy is simply
older, so the scan finds nothing new, and the scan after it copies again and
catches up. **Usage is delayed, never skipped**, because the checkpoint only
ever advances over timestamps a scan actually read.

#### A0 — the rules, and why each one

**Implemented.** `DataDirectoryResolver` in `collectors/opencode/locator.py`,
held by the collector instance. Measured: an OpenCode scan went from 900 ms to
276 ms, and `/api/collector/status` from 759 ms to 194 ms. Four rules make it
safe, and each is mutation-checked — disabling any one of them fails the suite:

1. **Cache successes only.** A failed probe is never cached, so installing
   OpenCode later is noticed on the next scan. Measured cost of a failed probe:
   **0 ms** (the binary simply is not there), so there is nothing to save by
   caching failure.
2. **Cache on the collector instance, not in a module global.** The collector is
   long-lived, so this is process-lifetime reuse for free — and it keeps tests
   isolated, because several locator tests simulate the CLI answering. (A
   module-level cache would also be awkward: `Settings` is unhashable, so it
   cannot key an `lru_cache`.)
3. **Re-probe when the cached path stops holding `opencode.db`.** This is the
   self-healing rule that covers "the user moved their data directory" without a
   TTL, which would add invalidation to reason about and buy nothing measurable.
4. **Re-probe on manual rescan.** The escape hatch should cost nothing: the user
   reaches for rescan precisely when the numbers look wrong.

Do **not** persist the path to disk. The server is long-lived, so a restart costs
one probe either way, and a cache file outlives the process — strictly worse than
re-probing once at startup. This is exactly the kind of assumption §10 lists, and
it holds because the app runs locally.

**Scope note:** this affects `discover()` too, which costs ~583 ms for the same
reason and is on the path of every `GET /api/collector/status`.

#### A3 — what the cost actually was

This item was misdiagnosed when the plan was written. It assumed the timeline was
slow because it fetched ORM entities; it already selected plain columns. Profiling
showed the real cost: `_bucket_index` scanned the bucket edges **linearly, once per
row**. A day timeline over a year has ~280 edges, so the same 2,142 rows cost 45 ms
bucketed by day against 7 ms by month — the difference was the edge count, not the
data.

It is now a binary search over the same sorted edges: **43 ms → 8.2 ms**, with month
and year unchanged. `tests/test_timeline_bucketing.py` checks the fast
implementation against the original linear one for every edge, every boundary, both
ends of the range, and four timezones across a daylight-saving transition — where a
local day is not 24 hours long, and any fix that assumed evenly spaced UTC edges
would quietly misbucket.

**Still avoided:** pushing bucketing into SQL with a timezone offset. Across a DST
transition, day lengths in UTC are not uniform, so a fixed offset would produce
plausible, wrong numbers. The edge search stays exact.

Also measure `orjson` as a drop-in for the ~200 ms of JSON parsing, but do not
adopt it without a measurement.

### Phase B — parallel collection

**Scope: Cline only.** After phase A, OpenCode's remaining cost is almost
entirely variable-but-tiny (§1), and its sessions are 0.1 ms each. Batching it
would save ~8 ms and would need snapshot-sharing machinery that no current
platform requires (§4.3).

| # | Change |
|---|---|
| B1 | `CollectorBatch` + `iter_batches()` default in `collectors/base.py` |
| B2 | `sync/executor.py` — persistent process pool, longest-batch-first |
| B3 | `outcome=` keyword on `SyncService.run` |
| B4 | Coordinator batching path |
| B5 | Cline override only; measure peak RSS and confirm the gain is real |
| B6 | Conformance suite: a fake third platform, plus the N-platform projections in §3 |

**Deferred, recorded so it is not rediscovered painfully:** sharing one snapshot
across batches, and any OpenCode override. Both exist only to shard a
single-file SQLite source. The trigger to revisit is *a future platform with one
large database where measurement shows sharding helps* — and expect both to be
needed together when that day comes (§4.3).

**Gate between A and B — now due.** Phase A is complete. Re-run the benchmark
before starting B. On today's numbers B would apply to Cline alone, for ~31% of a
144 ms collection step (~59 ms), while a full pass is already down to ~250 ms. The
honest read is that B is insurance against growth rather than a fix for anything
felt now, and it should be built only if the measurements still call for it.

---

## 14. Tests

| Claim | How it is proven |
|---|---|
| Parallel output equals sequential output | Same fixture, both paths, byte-identical record sets |
| A failed batch never advances the checkpoint | Injected batch failure; assert the resume point and that a later scan recovers the records |
| Order does not matter | Shuffle batch completion order; assert identical storage |
| Pending messages survive batching | A batch reporting an in-flight message holds the checkpoint back, exactly as the sequential scan does (§6.4) |
| Re-running never inflates | Existing idempotence tests, re-run under the executor |
| A pool that cannot start still collects | Force pool construction to fail; assert sequential fallback |
| A new platform needs no `sync/` changes | The conformance suite in §11 |
| Optimisations actually helped | `scripts/benchmark_sync.py`, before/after, committed output |

**A0 specifically** (these are cheap and belong with the change, not after it):

| Claim | How it is proven |
|---|---|
| The CLI is asked once, not once per scan | Count `subprocess.run` calls across repeated scans on one collector |
| Failures are never cached | Simulate a missing CLI, then make it answerable; assert the next scan picks it up |
| A moved data directory self-heals | Resolve, delete the DB from the cached path, assert the next scan re-probes |
| An explicit setting still bypasses the CLI | Existing locator tests, unchanged |
| No cache leaks between collectors | A second collector instance probes again |

---

## 15. Risks

| Risk | Mitigation |
|---|---|
| Silent data loss from a partial scan | §6.2 checkpoint rule, tested; default to re-reading over skipping |
| Checkpoint written before records commit | Ordering unchanged from today's `SyncService`; the commit stays where it is |
| Pool leaks processes across restarts | Created in lifespan, shut down on exit |
| Worker crashes take down the scan | Caught per batch; recorded as a failed batch, surfaced in collector status |
| Fork + SQLite connection inheritance | Workers open their **own** `mode=ro` connection to a snapshot, never the live file. Cline's batches read separate files, so this does not arise today (§4.3) |
| Parallelism stealing CPU from the user | 4 workers on 8 cores, overridable, with sequential fallback. The machine belongs to the user (§9) |
| A0 caches a stale path after the user moves their config | Re-probe when the cached path stops holding the DB, and on manual rescan; successes only, never failures |
| Batching OpenCode, if ever attempted, takes 29 snapshots | Deferred by decision (§4.3), not by oversight. If revisited, snapshot sharing must land first |

---

## 16. Expected results

### Latency

Projections, to be measured in A0/A1 and confirmed in B6.

| Scenario | Today | After A | After A + B |
|---|---:|---:|---:|
| First import | ~1.3 s | ~0.35 s | ~0.25 s |
| Full rescan (writes dominate) | ~1.1 s | ~0.15 s | ~0.15 s |
| Steady-state scan | 103 ms | ~50 ms | ~40 ms |
| Timeline query | 43 ms | ~8 ms | ~8 ms |
| Collector status view | 759 ms | ~7 ms | ~7 ms |

### Cost per scan — the number that actually matters here

This runs locally with one user, so nothing is ever waiting on a scan. The
first import runs in the background while the user does something else. Latency
is therefore close to cosmetic, and the meaningful measure is **what a scan
costs**, because that sets how often it can run — and a tracker whose numbers
are minutes stale is not doing its job.

| | Today | After A | After A + B |
|---|---:|---:|---:|
| OpenCode, fixed cost | ~769 ms | ~0 ms | ~0 ms |
| OpenCode, variable | ~51 ms | ~51 ms | ~51 ms |
| Cline | ~144 ms | ~144 ms | ~85 ms |
| Write cost, re-import | ~1,125 ms | ~71 ms | ~71 ms |
| Status view (`GET /api/collector/status`) | 759 ms | ~7 ms | ~7 ms |
| Daily timeline query | 43 ms | ~8 ms | ~8 ms |
| **Cost of one full scan** | **~948 ms** | **~250 ms** | **~200 ms** |
| Status view, idle | 759 ms | ~7 ms | ~7 ms |
| Interval affordable at the same background cost | 5 min | ~1 min | ~30 s |
| Share of one core, continuously | 0.3% | 0.08% | 0.07% |

Note the shape: phase A removes **all** of OpenCode's fixed cost, because that
cost is one subprocess and one database copy, neither of which depends on how
many records exist. Phase B then attacks the only substantial variable cost left
— Cline's 144 ms — and OpenCode's 51 ms is not worth the machinery (§4.3).

So the payoff of A is not "the dashboard loads faster". It is that **the same
background cost buys five to ten times more frequent syncing**, which is the
thing a local tracker actually wants.

Honest caveat: the parallel ceiling measured today is −31% on Cline's collection
and roughly nothing elsewhere, because OpenCode's sessions are 0.1 ms each and
its real cost is fixed. **Phase A delivers more than phase B does**, for a
fraction of the risk. Phase B is about staying fast as platforms and history
grow, not about fixing today's numbers.

---

## 17. Open questions to settle during implementation

1. ~~A0 cache lifetime: per process, or TTL?~~ Settled: process lifetime, since
   the app is a long-lived local process and a restart costs one probe. Only
   successful answers are cached; a re-probe happens when the cached path stops
   holding `opencode.db`, and on manual rescan. The TTL experiment was dropped
   because it buys nothing measurable and adds invalidation to reason about.
2. ~~Should OpenCode be batched too?~~ Settled: no. Measured at 0.1 ms of
   parsing per session, worth ~8 ms across four workers, and it would require
   snapshot sharing that no current platform needs (§4.3).
3. A1: is `INSERT … ON CONFLICT` available on every SQLite the project must
   support, and what is the fallback if not?
4. B2: is `min(4, cpu_count − 1)` right, or should it scale with batch count?
5. B6: what is the real N-platform curve, measured rather than projected?
6. If the interval drops to ~30 s, does the snapshot rule (A2) still need to
   exist, or does scanning that often make staleness impossible anyway?
7. If a future platform turns out to have one large SQLite worth sharding, both
   deferred options in §4.3 are needed together — snapshot sharing *and* the
   override. Neither should be built before that platform exists.