# Lessons

Things this project learned by measuring instead of assuming. Each one is here
because it was believed wrong first, and the correction cost real time.

---

## 1. Profile before designing

**The lesson, in one line.** Parallel collection was the headline of a
three-phase performance plan. It turned out to be worth about **43 ms**. The
**742 ms** that actually mattered was fixed per-scan cost — one subprocess and
one database copy — and removing it needed no new machinery at all.

Collection of both platforms went from **948 ms to 206 ms** by deleting work,
not by adding concurrency.

### Three things believed before measuring

| Belief | What the measurement said |
|---|---|
| "Tokens are calculated sequentially, which is slow" | Summing tokens is **1.3 ms**. The arithmetic was never the bottleneck |
| "Parallelise across the two platforms" | Worth **11%**, because the larger platform dominates the pass |
| "The timeline is slow because it fetches ORM entities" | It already selected plain columns. The cost was scanning bucket edges linearly, once per row |

All three came from reading the code carefully. None came from running it.
Profiling each stage and ranking by size found the real target in minutes; the
design that followed was smaller than the one we had planned.

### Fixed cost versus variable cost

Separate what a run **always** pays from what grows with the data. This decides
the whole approach:

| | Fixed per run | Variable per run | Does parallelism reach it? |
|---|---:|---:|---|
| OpenCode scan | ~769 ms (subprocess + database copy) | ~51 ms | **No** — only the 51 ms |
| Cline scan | 0 ms | ~144 ms | **Yes** |

A **fixed** cost is removed by not doing the work — caching, skipping, deleting.
A **variable** cost is what parallelism is for. Measuring which one you are
looking at decides the answer, and usually the answer is the cheaper one.

### Three questions before building anything for speed

1. **Which stage is largest?** Measure it. Do not infer it from reading the code —
   all three beliefs above came from careful reading and all three were wrong.
2. **Is it fixed or variable?** If fixed, no amount of concurrency helps.
3. **Would this change target the largest number in the table?** If not, it is not
   the work to do next, however interesting it is.

---

## 2. Price the maintenance, not the diff

A process pool is about fifty lines. It is also a process pool: lifecycle,
failure modes, inter-process communication, a single-writer commit barrier, and a
conformance suite to keep it honest — all of it permanent.

`parallelism.md` §13 is the worked example. Phase B would have saved ~43 ms in
exchange for all of that, on a pass that phase A had already brought to 206 ms.
So it was **held** rather than built, and the conditions that would reopen it are
recorded instead of a vague intention.

A held plan is not a failed plan. It is a decision, and it should be written down
with its reasoning and its exit conditions so nobody has to re-derive it.

---

## 3. Measure the thing you are about to claim

Every performance number in this project was measured on the real stores, not
estimated. Some that changed the plan when checked:

- `opencode debug paths` costs ~590 ms per call — not the small check it looked like
- OpenCode's 29 sessions carry ~11 ms of parsing **in total**, 0.1 ms each
- Eight processes reading one read-only SQLite snapshot concurrently all agree, so
  sharing a snapshot across workers is safe
- Pickling 2,142 usage records costs 25 ms — not worth designing an IPC layer for

The third one prevented a bug: OpenCode runs in WAL mode, so new usage lands in
`opencode.db-wal` and the main file looks untouched. Fingerprinting only the main
file would have reused a copy that was missing the very records it was asked to
find.

---

## 4. Verify the fix, then verify the test

Two habits that caught real problems in this project:

- **Mutation-test new tests.** Disable the behaviour and confirm the test fails.
  Three tests written to guard the caching rules passed just as happily when the
  rules were removed, until each rule was individually disabled and seen to break
  one. A test that cannot fail is decoration.
- **Re-run the full suite in a second shape.** Running with no Cline store
  installed found a scheduler test that passed alone and failed under load —
  because it assumed 50 ms was enough. A test that passes alone is not necessarily
  correct.

---

## 5. State the window, or widen it

The range filter defaulted to the last seven days. The model breakdown labelled
itself "Totals for last 7 days"; the four charts above it said only "Tokens per
calendar day", so a seven-day chart could be read as the whole history.

Every panel now names the window it covers. Widening the default was the wrong
fix: all-time would give a daily chart 365 buckets for two weeks of history, and
a sparse chart is its own kind of misleading. **State the truth rather than hide
it behind a default.**