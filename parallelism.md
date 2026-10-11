# Parallelism.md — making collection fast, and keeping it fast as platforms are added

**Status:** plan. Nothing in this document is implemented yet.

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

| Stage | Time | Note |
|---|---:|---|
| **OpenCode `collect_history()`** | **836 ms** | |
| ↳ `opencode debug paths` subprocess | ~597 ms | **71% of it** — runs on *every* scan |
| ↳ snapshot copy of the live database | ~172 ms | a full copy, every scan |
| ↳ indexed SQL query | 11 ms | `message_session_time_created_id_idx` already exists |
| ↳ `json.loads` + normalize in Python | ~100 ms | |
| **Cline `collect_history()`** | **144 ms** | |
| ↳ read + `json.loads` of 42 session files | ~100 ms | |
| ↳ normalize in Python | ~33 ms | |
| **Sequential total** | **948 ms** | |
| Write: first import, 2,142 rows | 174 ms | one transaction |
| Write: re-import 2,142 existing rows | **1,125 ms** | one `UPDATE` per row |
| Dashboard `summary` / `breakdown` / `timeline` | 1.3 / 2.4 / 43 ms | |

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

Three consequences shape the design:

- **Parallelising across platforms buys ~11% today.** OpenCode dominates, so
  Amdahl caps the win at whatever the smaller collector costs. It is not worth
  machinery on its own.
- **Threads do not work.** `json.loads` and model construction hold the GIL; four
  threads measuring *slower* than one is the expected result, and it was
  observed. Only processes help. (One exception noted in §8.)
- **The parallelism that pays is inside a collector**, where units are genuinely
  independent: Cline has 42 session files, OpenCode has 29 indexed sessions.

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
changes** on day one; each opts in later by overriding one method.

### 4.3 Overriding it, per platform

```python
# collectors/cline/collector.py — 42 independent files become 42 batches
def iter_batches(self, checkpoint=None) -> list[CollectorBatch]:
    return [
        CollectorBatch(key=session_id, collect=partial(self._batch, session_id))
        for session_id in self._session_ids()
    ]
```

```python
# collectors/opencode/collector.py — 29 indexed sessions become 29 batches
# message_session_time_created_id_idx on (session_id, time_created, id) means a
# per-session query is an index range scan, not a table scan.
def iter_batches(self, checkpoint=None) -> list[CollectorBatch]:
    with self._snapshot_connection(...) as connection:
        return [
            CollectorBatch(key=session.session_id, collect=partial(self._batch, session.session_id))
            for session in list_sessions(connection)
        ]
```

Verified: **8 processes reading one read-only snapshot concurrently all returned
identical results**, so sharing a snapshot across workers is safe. Each worker
opens its own `mode=ro` connection.

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

**6.4 Idempotence absorbs the rest.** Re-running is safe because the upsert
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
   collector that does not override it still works, just as one batch.
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
| `collectors/opencode/collector.py` | override `iter_batches()` (opt-in) | Medium — as above |
| `collectors/opencode/reader.py` | per-session message query | Low |

No file is deleted, renamed, or restructured. No new dependency is added.

---

## 13. Rollout

Each phase is independently shippable and independently measurable. Stop after
any of them.

### Phase A — the bottlenecks (no architecture change)

| # | Change | Expected | Risk |
|---|---|---|---|
| **A0** | Cache the resolved OpenCode data directory instead of re-running `opencode debug paths` per scan | **−590 ms per scan and per status view** | See the rules below |
| A1 | Replace the per-row `UPDATE` loop with one bulk `INSERT … ON CONFLICT DO UPDATE` | 1,125 → ~60 ms | Needs SQLite ≥ 3.24 (2018). Must preserve `UpsertResult` counts. |
| A2 | Skip the snapshot when the live DB is unchanged (`mtime`, `size`) | −172 ms per no-change scan | A stale snapshot must never skip new messages; the timestamp checkpoint makes this safe, and needs a test proving it. |
| A3 | Timeline: select columns instead of ORM entities | 43 → ~8 ms | Low |

#### A0 — the rules, and why each one

A0 is the largest single win in the whole plan and the smallest change. Four
rules make it safe:

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

**A3 trap, flagged now:** the tempting fix — pushing bucketing into SQL with a
timezone offset — is wrong across DST, where day lengths in UTC are not uniform.
Do the safe tuple-based fix; treat SQL bucketing as a separate decision.

Also measure `orjson` as a drop-in for the ~200 ms of JSON parsing, but do not
adopt it without a measurement.

### Phase B — parallel collection

| # | Change |
|---|---|
| B1 | `CollectorBatch` + `iter_batches()` default in `collectors/base.py` |
| B2 | `sync/executor.py` — persistent process pool, longest-batch-first |
| B3 | `outcome=` keyword on `SyncService.run` |
| B4 | Coordinator batching path |
| B5 | Per-platform overrides (Cline, then OpenCode); measure peak RSS |
| B6 | Conformance suite: a fake third platform, plus the N-platform projections in §3 |

**Gate between A and B.** After A, re-run the benchmark. If collection is already
comfortably fast for real usage, stop — phase B is insurance against growth, not
a fix for a problem felt today. It should be built only if the numbers justify
it.

---

## 14. Tests

| Claim | How it is proven |
|---|---|
| Parallel output equals sequential output | Same fixture, both paths, byte-identical record sets |
| A failed batch never advances the checkpoint | Injected batch failure; assert the resume point and that a later scan recovers the records |
| Order does not matter | Shuffle batch completion order; assert identical storage |
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
| Fork + SQLite connection inheritance | Workers open their **own** `mode=ro` connection to a snapshot, never the live file |
| Parallelism stealing CPU from the user | 4 workers on 8 cores, overridable, with sequential fallback. The machine belongs to the user (§9) |
| A0 caches a stale path after the user moves their config | Re-probe when the cached path stops holding the DB, and on manual rescan; successes only, never failures |

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

### Cost per scan — the number that actually matters here

This runs locally with one user, so nothing is ever waiting on a scan. The
first import runs in the background while the user does something else. Latency
is therefore close to cosmetic, and the meaningful measure is **what a scan
costs**, because that sets how often it can run — and a tracker whose numbers
are minutes stale is not doing its job.

| | Today | After A | After A + B |
|---|---:|---:|---:|
| Cost of one full scan | ~948 ms | ~250 ms | ~200 ms |
| Interval affordable at the same background cost | 5 min | ~1 min | ~30 s |
| Share of one core, continuously | 0.3% | 0.08% | 0.07% |

So the payoff of A is not "the dashboard loads faster". It is that **the same
background cost buys five to ten times more frequent syncing**, which is the
thing a local tracker actually wants.

Honest caveat: the parallel ceiling measured today is −31% on collection, and
almost all of that comes from Cline's 42 independent files. **Phase A delivers
more than phase B does**, for a fraction of the risk. Phase B is about staying
fast as platforms and history grow, not about fixing today's numbers.

---

## 17. Open questions to settle during implementation

1. ~~A0 cache lifetime: per process, or TTL?~~ Settled: process lifetime, since
   the app is a long-lived local process and a restart costs one probe. Only
   successful answers are cached; a re-probe happens when the cached path stops
   holding `opencode.db`, and on manual rescan. The TTL experiment was dropped
   because it buys nothing measurable and adds invalidation to reason about.
2. A1: is `INSERT … ON CONFLICT` available on every SQLite the project must
   support, and what is the fallback if not?
3. B2: is `min(4, cpu_count − 1)` right, or should it scale with batch count?
4. B6: what is the real N-platform curve, measured rather than projected?
5. If the interval drops to ~30 s, does the snapshot rule (A2) still need to
   exist, or does scanning that often make staleness impossible anyway?