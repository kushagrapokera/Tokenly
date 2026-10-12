"""The `myusage` command: auto-configure, sync, then answer usage questions.

The only module that reads input or prints. It wires together the pure pieces —
`cli.discovery` (find the data dirs), the existing sync coordinator (update the
database), and `cli.reports` (the queries) — behind a numbered, cross-platform menu.
"""

import argparse
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from aggregation.breakdown import ModelUsage
from aggregation.summary import UsageSummary
from cli import discovery, prompts, reports, tables
from collectors.registry import build_collectors
from database.connection import create_database_engine, create_session_factory
from database.schema import ensure_schema
from sync.coordinator import build_sync_coordinator

UI_URL = "http://127.0.0.1:8000"
API_URL = "http://127.0.0.1:8000"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="myusage", description="Local token usage for your AI coding assistants."
    )
    parser.add_argument(
        "--rediscover", action="store_true", help="re-run auto-discovery and overwrite saved config"
    )
    parser.add_argument(
        "--no-sync", action="store_true", help="skip syncing; report on already-stored data"
    )
    parser.add_argument("--link", action="store_true", help="print the dashboard links and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the `myusage` console command."""
    args = parse_args(argv)

    paths = discovery.discover_paths(force=args.rediscover)
    _print_discovered(paths)

    settings = discovery.build_settings(paths)
    try:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"Could not prepare the database directory: {error}")
        return 1

    engine = create_database_engine(settings.database_url, database_path=settings.database_path)
    try:
        ensure_schema(engine)
        session_factory = create_session_factory(engine)

        if not args.no_sync:
            _sync(settings, session_factory)

        _print_links()
        if args.link:
            return 0

        _interactive(settings, session_factory)
        return 0
    finally:
        engine.dispose()


def _sync(settings, session_factory: sessionmaker[Session]) -> None:
    """Run one sync pass over every available platform."""
    print("\nSyncing OpenCode, Cline, Claude Code, Codex ...")
    collectors = build_collectors(settings)
    try:
        coordinator = build_sync_coordinator(collectors, settings)
        for result in coordinator.run_all(session_factory):
            if result.failed:
                print(f"  {result.platform}: sync failed - {result.error_message}")
            elif result.stored:
                print(f"  {result.platform}: +{result.stored} record(s)")
            else:
                print(f"  {result.platform}: up to date")
    finally:
        # A collector may be holding a copy of its source database. The command is
        # about to exit, so there is no reason to leave that copy on disk.
        for collector in collectors:
            collector.close()


def _print_discovered(paths: discovery.DiscoveredPaths) -> None:
    """Show which data directory each platform resolved to."""
    print("\nConfigured from your system:")
    found: list[tuple[str, Path | None]] = [
        ("Codex", paths.codex_home),
        ("Claude Code", paths.claude_data_dir),
        ("Cline", paths.cline_data_dir),
        ("OpenCode", paths.opencode_data_dir),
    ]
    tables.print_table(
        [
            tables.Column("Tool", right=False, priority=1),
            tables.Column("Data directory", right=False, priority=1),
        ],
        [[name, str(path) if path else "(not found)"] for name, path in found],
    )


def _print_links() -> None:
    print(f"\nDashboard:  {UI_URL}    (API: {API_URL})")


def _interactive(settings, session_factory: sessionmaker[Session]) -> None:
    timezone_name = settings.default_timezone
    with session_factory() as session:
        while True:
            choice = prompts.choose(
                "\nWhat do you want to see?",
                [("model", "Model-wise"), ("provider", "Provider-wise")],
            )
            if choice is None:
                print("Bye.")
                return
            if choice == "model":
                _model_flow(session, timezone_name)
            else:
                _provider_flow(session, timezone_name)


def _model_flow(session: Session, timezone_name: str) -> None:
    models = reports.available_models(session)
    if not models:
        print("No model usage recorded yet.")
        return
    chosen = prompts.choose("\nPick a model:", _choice_options(models))
    if chosen is None:
        return
    print(f"\n{chosen}")
    _print_summary_table(reports.model_report(session, chosen, timezone_name))


def _provider_flow(session: Session, timezone_name: str) -> None:
    providers = reports.available_providers(session)
    if not providers:
        print("No provider usage recorded yet.")
        return
    chosen = prompts.choose("\nPick a provider:", _choice_options(providers))
    if chosen is None:
        return
    print(f"\nProvider: {chosen}")
    _print_provider_report(reports.provider_report(session, chosen, timezone_name))


# --- plain-ASCII formatting (no Unicode box drawing: safe on Windows cp1252) ---


def _requests(count: int) -> str:
    return f"{count} request" + ("" if count == 1 else "s")


def _percent(fraction: float | None) -> str:
    """Render a rate as a percentage, or a dash when there is no data to divide by."""
    return "-" if fraction is None else f"{fraction * 100:.1f}%"


def _choice_options(pairs: list[tuple[str, int]]) -> list[tuple[str, str]]:
    """Build menu labels whose counts line up in a column.

    Names are trimmed so the counts still align in a narrow terminal; the full name is
    still what gets chosen and reported afterwards, so nothing is lost but the display.
    """
    budget = tables.terminal_width() - 24
    tally_width = max(len(_requests(count)) for _, count in pairs)
    name_width = max(len(name) for name, _ in pairs)
    shown = max(12, min(name_width, budget - tally_width - 12))
    return [
        (name, f"{_short_name(name, shown)}  {_requests(count).rjust(tally_width)}")
        for name, count in pairs
    ]


def _short_name(name: str, width: int) -> str:
    """Trim a name to the menu's width, marking it so a cut name is never read as whole."""
    if len(name) <= width:
        return name.ljust(width)
    return name[: width - 1] + tables.ELLIPSIS


def _summary_columns() -> list[tables.Column]:
    """Describe the window table, most important column first."""
    return [
        tables.Column("Window", right=False, priority=1),
        tables.Column("Requests", priority=1),
        tables.Column("Total", priority=1),
        tables.Column("Input", priority=2),
        tables.Column("Output", priority=2),
        tables.Column("Consumption", priority=2),
        tables.Column("HitRate", priority=3),
        tables.Column("TokenHit", priority=3),
        tables.Column("CacheRead", priority=4),
        tables.Column("Hits", priority=4),
        tables.Column("Misses", priority=4),
        tables.Column("Unknown", priority=4),
    ]


def _summary_rows(rows: list[tuple[str, UsageSummary]]) -> list[list[str]]:
    """Flatten summaries into the plain strings the table lays out."""
    return [
        [
            label,
            f"{summary.request_count:,}",
            f"{summary.total_tokens:,}",
            f"{summary.input_tokens:,}",
            f"{summary.output_tokens:,}",
            f"{summary.consumption_tokens:,}",
            _percent(summary.cache.request_hit_rate),
            _percent(summary.cache.token_hit_rate),
            f"{summary.cache.cache_read_tokens:,}",
            f"{summary.cache.cache_hit_requests:,}",
            f"{summary.cache.cache_miss_requests:,}",
            f"{summary.cache.cache_unknown_requests:,}",
        ]
        for label, summary in rows
    ]


def _print_summary_table(rows: list[tuple[str, UsageSummary]]) -> None:
    """Print one row per window, dropping the least important columns when space is short."""
    if not rows:
        print("(no usage in this range)")
        return
    tables.print_table(_summary_columns(), _summary_rows(rows))


def _provider_columns() -> list[tables.Column]:
    """Describe the per-provider model table, most important column first."""
    return [
        tables.Column("Model", right=False, priority=1),
        tables.Column("Requests", priority=1),
        tables.Column("Total", priority=1),
        tables.Column("Consumption", priority=2),
        tables.Column("HitRate", priority=3),
        tables.Column("TokenHit", priority=3),
        tables.Column("CacheRead", priority=4),
        tables.Column("Hits", priority=4),
        tables.Column("Misses", priority=4),
    ]


def _print_provider_report(rows: list[tuple[str, list[ModelUsage]]]) -> None:
    """Print a table of models per provider, fitting whatever width is available."""
    for label, model_rows in rows:
        print(f"\n  {label}")
        if not model_rows:
            print("    (no usage)")
            continue
        tables.print_table(
            _provider_columns(),
            [
                [
                    model.model_id,
                    f"{model.request_count:,}",
                    f"{model.total_tokens:,}",
                    f"{model.consumption_tokens:,}",
                    _percent(model.cache.request_hit_rate),
                    _percent(model.cache.token_hit_rate),
                    f"{model.cache.cache_read_tokens:,}",
                    f"{model.cache.cache_hit_requests:,}",
                    f"{model.cache.cache_miss_requests:,}",
                ]
                for model in model_rows
            ],
        )


if __name__ == "__main__":
    raise SystemExit(main())

