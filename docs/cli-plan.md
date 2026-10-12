# Tokenly CLI — `myusage` Implementation Plan

A terminal companion to the dashboard: one command that syncs the database, prints
the dashboard link, and answers quick token-usage questions (model-wise or
provider-wise) across Today / Last 7 days / This month / Last month / All time.

**Guiding constraints (from `AGENTS.md` and prior phases):** reuse the existing
sync + aggregation code, add **no new dependencies**, keep the CLI cross-platform
(macOS / Windows / Linux), and make it **zero-config** — a fresh clone discovers
each tool's data automatically and remembers it.

---

## 1. Goal

Turn `myusage` into a self-configuring, read-only usage reporter that:
1. Auto-discovers where OpenCode, Cline, Claude Code, and Codex CLI store their
   data on the current machine (no manual env vars or symlinks).
2. Syncs the local `data/tokenly.db` with the latest data.
3. Prints the dashboard links.
4. Offers an interactive Q&A: **model-wise** or **provider-wise** stats over
   selectable time windows.

## 2. What the user runs

```bash
pip install -e .        # one-time; creates the `myusage` launcher
myusage                 # auto-configures (first run), syncs, then Q&A
```

Optional flags:
- `myusage --rediscover` — re-run auto-discovery and overwrite the saved config.
- `myusage --no-sync` — skip the sync step and just report on stored data.
- `myusage --link` — print only the dashboard links and exit.

## 3. Command flow

```
myusage
  ├─ 1. Load config (or auto-discover on first run) ──► cli/discovery.py
  ├─ 2. Sync all platforms into data/tokenly.db     ──► reuse sync coordinator
  ├─ 3. Print dashboard links (UI + API)
  └─ 4. Interactive Q&A                              ──► cli/myusage.py
         ├─ "Model-wise"  → pick a model  → stats per window
         └─ "Provider-wise" → pick a provider → per-model split per window
```

## 4. Auto-discovery & auto-configuration

Discovery runs **before** sync, in this order per platform:

1. **Saved config** (from a previous run) — instant, no filesystem search.
2. **Explicit environment variable** — `CODEX_HOME`, `CLAUDE_CONFIG_DIR` (only
   these two platforms have documented env vars).
3. **Platform default** — computed by each locator, cross-platform.
4. **Bounded filesystem search** for the platform's signature (only if 1–3 miss).

The first time discovery succeeds it **writes the found paths to a config file**
and prints them, e.g.:

```
Auto-configured from your system:
  Codex       → /home/you/Desktop/Projects/codex
  Claude Code → /home/you/.claude
  Cline       → /home/you/.cline/data
  OpenCode    → /home/you/.local/share/opencode
Saved to ~/.config/tokenly/config.json (edit or run `myusage --rediscover`).
```

Later runs read the config; a stored path that no longer exists triggers a
re-search for just that platform. Discovered paths are passed into
`Settings(codex_home=…, claude_data_dir=…, cline_data_dir=…, opencode_data_dir=…)`.

## 5. Per-platform signatures (reuse each locator's defaults + env vars)

| Platform | Env var | Default (per OS) | Search signature |
|---|---|---|---|
| Codex | `CODEX_HOME` | `~/.codex` | a `sessions/` dir containing `**/rollout-*.jsonl` |
| Claude Code | `CLAUDE_CONFIG_DIR` | `~/.claude` | `projects/*.jsonl` |
| Cline | — | `~/.cline/data` / `%LOCALAPPDATA%\cline\data` | `sessions/` + `db/sessions.db` |
| OpenCode | — | `~/.local/share/opencode` (or `opencode debug paths`) | `opencode.db` |

Discovery reuses `platform_default_data_directory()` from each locator rather
than re-implementing the per-OS defaults.

## 6. Config file — cross-platform, no new dependency

- Location (stdlib only):
  - Windows: `%APPDATA%\tokenly\config.json`
  - macOS: `~/Library/Application Support/tokenly/config.json`
  - Linux: `${XDG_CONFIG_HOME:-~/.config}/tokenly/config.json`
- Format: **JSON** (stdlib `json`; avoids adding `tomli_w`). Shape:
  ```json
  { "codex_home": "...", "claude_data_dir": "...",
    "cline_data_dir": "...", "opencode_data_dir": "..." }
  ```
- Missing/absent platforms are simply omitted (a user without Cline is normal).

## 7. Bounded search — safe & fast

Per `LESSONS.md` (profile, cap, don't scan blindly):
- Roots: `~` plus a small curated list (`~/Desktop`, `~/Documents`, `~/Projects`,
  `~/source`, `~/repos`, `~/code`, `~/dev`).
- Limits: **max depth ~6**, **max ~20,000 directories visited**, **~4s wall-clock
  budget**, results sorted for determinism.
- **Skip** noisy/huge dirs: `.git`, `node_modules`, `.venv`, `Library`, `AppData`,
  `__pycache__`.
- Runs **at most once** per platform (cached in the config file). `--rediscover`
  forces it again.

## 8. OS independence (non-negotiable)

The CLI must behave identically on **Linux, macOS, and Windows** with no per-OS
setup. This is a hard constraint, not a nice-to-have; the rules below are binding
and §17's checklist enforces them. Nothing may branch on the OS unless the branch
is *tested on every host* by monkeypatching `os.name`/`sys.platform`/`Path.home`
(see §14) — and the only allowed branches are the per-OS default/config-directory
lookups, which are centralized in one place.

**Install / launcher**
- Console entry point via `pip install -e .` produces the correct launcher per OS
  (`.venv/bin/myusage` on Unix, `.venv\Scripts\myusage.exe` on Windows). No shell
  shim, no shebang reliance, no `chmod +x` step for the user.

**Paths (the #1 source of OS bugs)**
- `pathlib.Path` everywhere; join with `/` operator or `.joinpath()`, **never**
  string concatenation, never hardcoded `/`, `\`, or drive letters.
- Home and config dirs come from a single cross-platform resolver
  (`Path.home()`, `%APPDATA%`, `~/Library/Application Support`, `${XDG_CONFIG_HOME:-~/.config}`)
  — no hardcoded `~/.config` or `C:\…` anywhere.
- All config files opened with `encoding="utf-8"`.
- Compare paths only after `Path.resolve()`; do **not** rely on case-sensitive
  equality (macOS/Windows filesystems are commonly case-insensitive).

**Filesystem search (discovery)**
- Catch and skip `OSError`/`PermissionError` per entry (Windows ACLs, macOS TCC
  privacy prompts, locked files) — a denied directory never aborts the scan.
- Skip-list matched **case-insensitively** (`.git`, `node_modules`, `.venv`,
  `Library`, `AppData`, `__pycache__`), since names can differ in case on some OSes.
- Never *require* a symlink (Windows needs elevated/Developer Mode); discovery
  falls back to the bounded search instead.

**Environment & subprocess**
- Env vars read via `os.environ.get("CODEX_HOME")` etc. (works on all OSes; Windows
  treats names case-insensitively). Absent var ⇒ fall through, never crash.
- Any subprocess (e.g. OpenCode's `debug paths`) passes an **argv list**, never
  `shell=True`, and tolerates a missing binary/`.exe`/`.cmd` by degrading to the
  default — never raising.

**Interaction & output**
- Numbered `input()` menus only (no curses/TUI, which needs `windows-curses`).
- Handle `EOFError` and `KeyboardInterrupt` to exit cleanly (Ctrl-D on Unix,
  Ctrl-Z+Enter on Windows).
- Plain ASCII output; no `os.system("clear"/"cls")`, no ANSI color, no Unicode box
  drawing (breaks on Windows `cp1252`). Numbers via `f"{n:,}"`.
- Timezone from `Settings.default_timezone`; all datetimes tz-aware (no naive
  local-time math that differs across OSes).

**Verification checklist (part of Definition of Done)**
- [ ] No hardcoded path separators or absolute OS paths in `cli/`.
- [ ] All filesystem access wraps `OSError` and skips on permission errors.
- [ ] Config dir resolves correctly under simulated Windows/macOS/Linux envs.
- [ ] Discovery + search pass with a monkeypatched non-Unix `os.name`/`Path.home`.
- [ ] Clean exit on `EOFError`/`KeyboardInterrupt`.


## 9. Installation (packaging changes)

Add to `pyproject.toml`:
- `[build-system]` (setuptools).
- `[project.scripts] myusage = "cli.myusage:main"`.
- An explicit setuptools `packages` list (include `cli`).
- Bump `version` `0.1.0` → `1.0.0` (align with `Settings.app_version`).

---

## 10. File structure (new top-level concern `cli/`)

```
cli/
  __init__.py
  myusage.py     # orchestration: discover → sync → links → interactive loop
  discovery.py   # auto-discovery + config read/write (JSON) + bounded search
  prompts.py     # numbered-menu / selection helpers (stdlib input())
  reports.py     # PURE data layer: given a Session + choice → report rows
tests/cli/
  __init__.py
  test_discovery.py
  test_reports.py
  test_prompts.py
pyproject.toml   # build-system + scripts + packages + version 1.0.0
```

Design rules:
- `reports.py` is **pure** (takes a `Session`, returns data) so it is unit-tested
  without touching `input()` or printing.
- `myusage.py` is the only module that reads `input()` and prints.
- Shared collectors, locators, `Settings`, aggregation, and sync are **not
  modified** — discovery lives entirely in the CLI and feeds `Settings`.

## 11. Reuse (no new logic, no new dependencies)

- **Sync:** `build_collectors(settings)` + `build_sync_coordinator(...).run_all(...)`.
- **DB setup:** `create_database_engine` + `create_session_factory` +
  `ensure_schema` (same as `main.py`).
- **Stats:** `summarize_range(session, window, UsageFilter(...))` and
  `breakdown_by_model(session, window, UsageFilter(...))`; windows via
  `resolve_range(name, tz)`.
- **Discovery defaults:** each locator's `platform_default_data_directory()`.
- Runtime deps unchanged (fastapi/uvicorn/sqlalchemy/alembic/pydantic-settings).
  The CLI itself uses only the standard library for I/O and interaction.

## 12. Output format / stats shown

**Model-wise** (after picking one model): a small table per window —
`requests · input · output · total tokens · consumption` for
**All time · Today · Last 7 days · This month · Last month**.

**Provider-wise** (after picking one provider): a per-model split of
`total tokens` (and requests) across those same windows, e.g.

```
Provider: deepseek          Today    Last 7d    This month    Last month
  deepseek-flash          120,000   3,410,432   33,332,360     9,120,000
  deepseek-reasoner         1,500      40,100      210,900      55,300
```

Example session:

```
$ myusage
Auto-configured from your system: … (first run only)
Syncing OpenCode, Cline, Claude Code, Codex … done (612 records stored).

Dashboard:  http://localhost:5173   (API: http://127.0.0.1:8000)

What do you want to see?
  1) Model-wise
  2) Provider-wise
  0) Exit
> 1

Models:
  1) deepseek-flash        (229 requests)
  2) claude-sonnet-4-5      (58 requests)
> 1

deepseek-flash
  Window        Requests    Input      Output   Total tokens   Consumption
  All time           229   33092737    239623      33332360     33332360
  Today                3      ...
  Last 7 days        ...
  This month         ...
  Last month         ...
```

## 13. Time windows

`All time · Today · Last 7 days · This month · Last month`. Both month variants are
shown so "last month" is unambiguous (maps to `current_month` / `previous_month`).

## 14. Tests

- `test_discovery.py`: non-default location found via bounded search; config
  round-trip (write/read); per-OS default dirs (monkeypatched `os.name`/`Path.home`);
  noisy-dir skip; depth cap; `--rediscover` overwrite; env-var precedence.
- `test_reports.py`: model summary and provider→model split over each window,
  seeded with a temp DB via the existing store builders.
- `test_prompts.py`: menu parsing and selection validation.

## 15. Assumptions & defaults

- Numbers are read from `data/tokenly.db`; the CLI resolves that path relative to
  the installed package so it works from any working directory.
- The dashboard links are printed as constants; the CLI does **not** start the
  frontend (it prints a hint if it isn't running).
- Platforms whose data isn't found are skipped with a one-line note, not an error.

## 16. Out of scope (future)

- Colorized output, tables via a TUI library, or a persistent interactive session.
- Modifying the backend/dashboard to consume this CLI.

## 17. Definition of done

- [ ] `pip install -e .` produces a working `myusage` on macOS, Windows, Linux.
- [ ] OS-independence checklist (§8) passes; no OS-specific code except the
      centralized per-OS default/config-dir lookups, each covered by a simulated-OS test.
- [ ] First run auto-discovers all present platforms and writes the config file.
- [ ] Subsequent runs are instant (no search) and stay correct if a path moves.
- [ ] Sync imports/updates the DB without duplicating records.
- [ ] Model-wise and provider-wise reports render correct per-window totals.
- [ ] Dashboard links printed.
- [ ] Unit tests pass; `ruff` clean; no new dependencies.
