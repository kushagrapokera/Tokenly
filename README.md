# Tokenly

**Local-first token usage tracker for AI coding assistants.**

Claude Code, Codex CLI, Cline and OpenCode already record every token they spend on
your machine, in their own session files. Tokenly reads those stores, normalises them
into one SQLite database, and shows you what you actually burned — by day, by model, by
provider, by assistant.

No account. No cloud. No telemetry. Your usage data never leaves your computer, and
Tokenly never writes to the assistants' own files.

---

## What you get

**A dashboard** at `http://127.0.0.1:8000` — served by the app itself as plain
HTML, CSS and JavaScript. No frontend build step, no `npm install`, no dependencies.
Four platform cards with trend sparklines, a stacked/grouped daily token chart with a
filterable legend, per-platform breakdown cards you can drill into per model, a model
ranking panel, and a CSV export.

**A terminal command**, `myusage` — the same numbers without the browser. It syncs,
then gives you numbered menus and tables that reflow to fit whatever width your
terminal happens to be.

```
  +-------------+----------+-----------+-----------+---------+-------------+---------+----------+
  | Window      | Requests |     Total |     Input |  Output | Consumption | HitRate | TokenHit |
  +-------------+----------+-----------+-----------+---------+-------------+---------+----------+
  | All time    |    2,887 | 7,583,593 | 6,657,027 | 926,566 | 465,325,515 |   99.3% |    98.6% |
  | Today       |      676 | 1,754,804 | 1,544,662 | 210,142 |  91,664,094 |   99.9% |    98.3% |
  | Last 7 days |    2,277 | 5,985,947 | 5,301,332 | 684,615 | 405,858,302 |   99.5% |    98.7% |
  +-------------+----------+-----------+-----------+---------+-------------+---------+----------+
```

Narrow the terminal and the table drops its least useful columns rather than wrapping,
down to three at a rough 46 columns. Widen it and the cache detail comes back.

---

## Requirements

- **Python 3.10 or newer**

That is the whole list. Tokenly runs whether or not you have any of the assistants
installed — each collector simply reports "not installed" and you get an empty dashboard
until you use one.

Five runtime dependencies: FastAPI, Uvicorn, SQLAlchemy, Alembic and pydantic-settings.

## Install

```bash
git clone https://github.com/kushagrapokera/Tokenly.git
cd Tokenly

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .          # provides the `myusage` command
```

The editable install is only needed for the CLI. If you would rather not install the
project, run it as a module instead:

```bash
.venv/bin/python -m cli.myusage     # same command, no install
```

## Run

```bash
.venv/bin/python main.py
```

Then open **http://127.0.0.1:8000**.

The first start imports whatever history your assistants already have, which can take a
few seconds on a large store. The dashboard stays reachable while it happens and shows
`scanning` on the status panel. After that it re-syncs every five minutes in the
background.

The CLI:

```bash
.venv/bin/myusage
```

| Flag | Effect |
|---|---|
| `--no-sync` | Skip the import and report only what is already stored |
| `--link` | Print the dashboard link and exit |
| `--rediscover` | Re-scan for the assistant data folders and overwrite the saved config |

---

## How it works

```
   ~/.claude        ~/.codex         ~/.cline/data       opencode's own path
        │              │                   │                        │
  collectors/claude  collectors/codex  collectors/cline   collectors/opencode
        └──────────────┴────────┬──────────┴────────────────────────┘
                               │
                    normalization/          canonical provider ids,
                    (providers,             category mapping, totals
                     categories, totals)
                               │
                               ▼
                     database/usage_events          one SQLite file
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
        aggregation/                      routes/ + web/  →  dashboard
   summary / breakdown /                  cli/reports.py  →  `myusage`
   timeline / cache rates
```

Each assistant stores things differently — different files, different schemas, one of
them in SQLite WAL mode. A **collector** per platform isolates that difference: it
locates the store, reads it, and emits the same shape of record as the other three. One
normalisation layer then folds those records onto shared provider ids and token
categories, and everything downstream — the API, the dashboard, the CLI — sees a single
schema.

Three of the four stores have a well-known default location. OpenCode's does not, so its
collector runs `opencode debug paths` once and caches the answer — worth about 600 ms
per scan otherwise — falling back to the platform default if that command is missing.

Two things worth knowing about the design:

**The assistants' files are opened read-only and never modified.** OpenCode's database
is live in WAL mode, so Tokenly asks SQLite's backup API for a consistent private copy
and reads that. The copy is reclaimed when the collector closes, when the object is
garbage collected, or — if the process was killed — by the next run, which sweeps
copies whose owning process is gone.

**Scans are incremental.** Each platform keeps a checkpoint, so a re-scan only reads
what is new. A checkpoint never advances past messages that are still generating, so
usage is delayed at worst, never skipped.

### API

A small JSON API under `/api`, all read-only except the rescan triggers:

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness and database reachability |
| `GET /api/usage/summary` | Totals for a range, with cache hit rates |
| `GET /api/usage/models` | Per-model breakdown, optionally scoped to a platform |
| `GET /api/usage/timeline` | Bucketed series for charting |
| `GET /api/usage/daily` · `/monthly` · `/yearly` | The same totals bucketed by calendar period |
| `GET /api/collector/status` | Per-platform discovery and last-sync state |
| `POST /api/collector/rescan` | Trigger a collection pass, for all platforms or one |

The API binds to `127.0.0.1` only and refuses cross-origin requests by default.
Interactive docs are served at `/docs`.

---

## Configuration

Everything has a working default. Override with environment variables or a `.env` file
in the project root; see `config/settings.py` for the full list.

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_PATH` | `data/tokenly.db` | Where the imported history lives |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Binding stays loopback by default |
| `DEFAULT_TIMEZONE` | `UTC` | Calendar edges are built in this zone |
| `SYNC_ENABLED` | `true` | Turn off to collect only on demand |
| `SYNC_INTERVAL_SECONDS` | `300` | Background refresh period |
| `OPENCODE_DATA_DIR` | auto-discovered | Point at a non-default OpenCode store |
| `CLAUDE_DATA_DIR` / `CLINE_DATA_DIR` / `CODEX_HOME` | auto-discovered | Same, per assistant |

To use the dashboard from a page served somewhere else, set `CORS_ALLOW_ORIGINS`
explicitly. It is empty by default, so no other origin can read your usage data.

---

## Test

```bash
.venv/bin/pip install -r requirements-dev.txt

.venv/bin/pytest          # backend: collectors, sync, aggregation, API
npm test                   # dashboard units
```

The Python suite runs against temporary databases and never reads your real assistant
stores, so it is safe to run anywhere. The JavaScript suite needs only Node's built-in
test runner — there are no dependencies to install.

```bash
.venv/bin/ruff check .     # lint
.venv/bin/mypy .           # types
npm run test:browser       # optional: drives a real page, needs `npm i -D puppeteer`
```

---

## Layout

One folder per concern.

| Path | Holds |
|---|---|
| `collectors/` | Per-platform storage adapters |
| `sync/` | Scan orchestration, checkpointing, scheduling |
| `normalization/` | Provider ids, category mapping, totals |
| `aggregation/` | Summary, breakdown, timeline, ranges, cache rates |
| `database/` | Engine, models, repository, progress state |
| `schemas/` | Pydantic request and response contracts |
| `routes/` | FastAPI routers, and the static file server for the dashboard |
| `web/` | The dashboard — plain HTML, CSS and JavaScript |
| `cli/` | The `myusage` command: discovery, prompts, reports, table layout |
| `config/`, `errors/`, `logging_setup/` | Settings, error types, logging |
| `tests/` | Backend tests, dashboard tests, integration tests |

The project rules live in `AGENTS.md`; it is kept per machine rather than in the repo.

---

## Privacy

Tokenly reads files that are already on your disk and writes only to its own database.
It opens every assistant store with SQLite's read-only mode, so the tools themselves
cannot be modified by it.

It makes no network requests of its own. The one subprocess it starts is
`opencode debug paths`, a local command, used once to find where OpenCode keeps its
data. The API binds to loopback and refuses cross-origin requests unless you explicitly
allow an origin.

## License

No licence file is published yet. Treat the repository as private until one is added.