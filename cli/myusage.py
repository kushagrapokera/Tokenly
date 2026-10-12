"""The `myusage` command: auto-configure, sync, then answer usage questions.

The only module that reads input or prints. It wires together the pure pieces —
`cli.discovery` (find the data dirs), the existing sync coordinator (update the
database), and `cli.reports` (the queries) — behind a numbered, cross-platform menu.
"""

import argparse

from sqlalchemy.orm import Session, sessionmaker

from aggregation.breakdown import ModelUsage
from aggregation.summary import UsageSummary
from cli import discovery, prompts, reports
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
    rows = [
        ("Codex", paths.codex_home),
        ("Claude Code", paths.claude_data_dir),
        ("Cline", paths.cline_data_dir),
        ("OpenCode", paths.opencode_data_dir),
    ]
    print("Configured from your system:")
    for label, path in rows:
        print(f"  {label:<12} {path if path else '(not found)'}")


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
    options = [(model, f"{model}  ({_requests(n)})") for model, n in models]
    chosen = prompts.choose("\nPick a model:", options)
    if chosen is None:
        return
    print(f"\n{chosen}")
    _print_summary_table(reports.model_report(session, chosen, timezone_name))


def _provider_flow(session: Session, timezone_name: str) -> None:
    providers = reports.available_providers(session)
    if not providers:
        print("No provider usage recorded yet.")
        return
    options = [(provider, f"{provider}  ({_requests(n)})") for provider, n in providers]
    chosen = prompts.choose("\nPick a provider:", options)
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


def _print_summary_table(rows: list[tuple[str, UsageSummary]]) -> None:
    header = (
        f"  {'Window':<12}{'Requests':>9}{'Input':>13}"
        f"{'Output':>11}{'Total':>15}{'Consumption':>15}"
    )
    cache_header = f"{'CacheRead':>15}{'Hit':>7}{'Miss':>7}{'Unk':>6}{'HitRate':>9}{'TokenHit':>10}"
    print(header + cache_header)
    for label, summary in rows:
        cache = summary.cache
        print(
            f"  {label:<12}{summary.request_count:>9}"
            f"{summary.input_tokens:>13,}{summary.output_tokens:>11,}"
            f"{summary.total_tokens:>15,}{summary.consumption_tokens:>15,}"
            f"{cache.cache_read_tokens:>15,}"
            f"{cache.cache_hit_requests:>7,}{cache.cache_miss_requests:>7,}"
            f"{cache.cache_unknown_requests:>6,}"
            f"{_percent(cache.request_hit_rate):>9}"
            f"{_percent(cache.token_hit_rate):>10}"
        )


def _print_provider_report(rows: list[tuple[str, list[ModelUsage]]]) -> None:
    header = (
        f"    {'model':<30}{'total_tokens':>15}{'cache_read':>15}"
        f"{'hit':>7}{'miss':>7}{'HitRate':>9}{'TokenHit':>9}"
    )
    for label, model_rows in rows:
        print(f"\n  {label}:")
        if not model_rows:
            print("    (no usage)")
            continue
        print(header)
        for model in model_rows:
            cache = model.cache
            print(
                f"    {model.model_id:<30}{model.total_tokens:>15,}"
                f"{cache.cache_read_tokens:>15,}"
                f"{cache.cache_hit_requests:>7,}{cache.cache_miss_requests:>7,}"
                f"{_percent(cache.request_hit_rate):>9}"
                f"{_percent(cache.token_hit_rate):>9}"
                f"  ({_requests(model.request_count)})"
            )


if __name__ == "__main__":
    raise SystemExit(main())

