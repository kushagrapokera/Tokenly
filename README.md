# Tokenly

Local-first token usage tracker for AI coding assistants. Reads the session stores
that Claude Code, Codex CLI, Cline, and OpenCode already write on your machine,
imports them into one SQLite database, and serves a dashboard and a CSV export.

No account, no network calls, no telemetry — the data never leaves the machine.

## Install

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python main.py          # API + dashboard on http://127.0.0.1:8000
.venv/bin/myusage                 # one-shot terminal report
```

The dashboard is served by the app itself from `web/`, so there is no separate
frontend build step and no JavaScript dependencies.

## Layout

One folder per concern:

| Folder | Concern |
|---|---|
| `collectors/` | Per-platform storage adapters (`claude`, `codex`, `cline`, `opencode`) |
| `sync/` | Scan orchestration, checkpointing, scheduling |
| `database/` | Engine, models, repository, progress state |
| `normalization/` | Provider ids, category mapping, totals |
| `aggregation/` | Summary, breakdown, timeline, ranges, cache rates |
| `schemas/` | Pydantic request/response contracts |
| `routes/` | FastAPI routers, including the `web/` asset server |
| `web/` | The dashboard (plain HTML/CSS/JS) |
| `cli/` | The `myusage` command |
| `config/`, `errors/`, `logging_setup/` | Settings, error types, logging |

## Configuration

Settings load from the environment or `.env`; see `config/settings.py`. Every
field is optional. `database_path` and the per-collector data directories are the
ones worth setting.

The API is same-origin by default and refuses cross-origin requests. Only set
`cors_allow_origins` if you serve a page from a different origin.

## Tests

```bash
.venv/bin/python -m pytest    # backend
npm test                      # dashboard units
```

`npm run test:browser` drives a real page with Puppeteer and needs it installed;
the unit suite has no dependencies.

## Conventions

Read [`AGENTS.md`](AGENTS.md) before changing anything. It holds the project rules
and points at the performance notes in [`docs/`](docs/).