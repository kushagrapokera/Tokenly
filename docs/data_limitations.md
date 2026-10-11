# Known data limitations

What Tokenly cannot tell you, and why. Written after validating against OpenCode's own
statistics on a live install; the numbers below are from that run.

Re-check at any time with:

```bash
python scripts/validate_against_opencode.py
```

It prints every model side by side and exits 0 only when all of them reconcile.

## Where Tokenly's numbers come from

Usage is read from one place: the `tokens` object on each assistant message in
OpenCode's SQLite database. Nothing else is consulted — not the `session` table, not
step-finish rollups, not provider pricing. Token counts therefore always mean what
OpenCode said they mean.

## 1. Reasoning tokens are counted separately, not inside "output"

OpenCode stores `reasoning` as its own field, distinct from `output`. Its own `total`
counts it as a separate additive term — verified on all 1,853 live records that state a
total, every one of which satisfies `input + output + reasoning + cache == total`.

`opencode stats`, however, shows no reasoning line and folds it into **Output Tokens**.
For the model validated here:

```
Tokenly  output 493,949 + reasoning 280,196 = 774,145
opencode stats  Output Tokens                   ≈  774K
```

**This is a presentation difference, not missing data.** Tokenly keeps the two apart
because folding them in would double-count against `consumption_tokens`. If you are
comparing against `opencode stats`, compare its Output Tokens against Tokenly's
`output + reasoning`.

Models that report no reasoning (`union-alpha`, `big-pickle`) match OpenCode exactly on
output, which is the control confirming this explanation.

## 2. Two token measures, and they are not interchangeable

| Measure | Meaning | Use for |
|---|---|---|
| `total_tokens` | `input + output` — what one call cost in prompt and completion tokens | Comparing across providers |
| `consumption_tokens` | `input + output + reasoning + cache_read` — everything actually processed | Understanding real usage and load |

`total_tokens` deliberately excludes reasoning and cache, because on OpenCode they are
additive rather than subsets. Adding them would inflate the per-call figure. Cache reads
in particular are large — 158.9M against 2.1M input on the model validated here — so
conflating the two overstates usage by roughly seventy-fold.

## 3. Cache write is always zero here

OpenCode reports `cache.write: 0` on every message on this install. Tokenly carries the
field and will report a real value if one ever appears; it is simply never non-zero
today. A zero means "not reported", not "definitively none".

## 4. Usage is only as current as the last sync

Tokenly has **no background sync**. Totals reflect whatever was collected last, so while
a session is running the dashboard under-reports until something triggers a scan. In
practice the dashboard holds the newest usage for up to the length of one session.

The validation run made this concrete: mid-session, five completed messages were
upstream but not yet stored. Running a sync cleared every difference and the script
returned 0. Messages still generating are correctly excluded and are not counted as a
discrepancy.

The in-flight guard is the mechanism behind this. OpenCode writes a message row when
generation *starts* and fills in tokens when it finishes, so the checkpoint is capped at
the oldest unfinished message rather than skipping past it.

## 5. A finished call that reported nothing counts as unknown, not zero

A completed message with no token counts is stored with null figures, contributes 0 to
every sum, and is reported through `unknown_total_events`. It is never silently read as
"no usage". The dashboard marks such cards **Partial** and each affected model row says
how many records reported no total.

One record on this install (`fledge-alpha-free`) is a genuine zero across every field.
It matches OpenCode exactly and is not a limitation.

## 6. Usage survives deletion; it is never removed

Nothing in Tokenly deletes a usage row. Session compaction and cleanup in OpenCode can
empty a session, and Tokenly keeps what that session cost. Validated directly: a full
rescan after deleting every source row left row count and totals unchanged.

The consequence is that totals are append-only over time. A model you stopped using
keeps contributing to its lifetime figure.

## 7. Only OpenCode is collected

One collector is registered. Codex CLI, Claude Code, Cline, and the rest are not
implemented, and the API will return 404 naming the platforms that do exist. The
architecture allows more; none are wired up.

## 8. Cost is out of scope

Nothing here is priced. Free hosted models and paid API models are tracked identically
and neither is special-cased. `opencode stats` reports `$0.0000` for all five models on
this install, which reflects its own pricing configuration rather than Tokenly's view.

## What validation confirmed

- Every model reconciles exactly on input, output, reasoning, and cache read.
- Message counts reconcile after a sync, ignoring in-flight messages.
- Reasoning is additive, proven arithmetically against OpenCode's own totals.
- Repeated syncs, full rescans, and simulated restarts never change a total.
- Deleted source history does not reduce stored usage.
