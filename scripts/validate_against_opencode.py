"""Compare Tokenly's stored usage with OpenCode's own numbers.

Run it against a real install:

    python scripts/validate_against_opencode.py

It reads both databases read-only and reports, per model, how Tokenly's figures relate
to OpenCode's. The comparison is not a plain equality check, because the two count
different things: OpenCode's CLI folds reasoning tokens into its "Output Tokens" line
and never shows the reasoning figure separately. This script states that relationship
instead of hiding it behind a pass/fail.

Two kinds of difference are reported separately, because they mean different things:

  * **Incorrect** — a token figure disagrees. That is a bug in Tokenly.
  * **Not yet synced** — a completed message exists upstream that Tokenly has not read.
    That is staleness, not wrongness: Tokenly has no background sync, so it reflects
    whatever was collected last. Running a sync should clear it.

Exit status is 0 when every model reconciles, 1 when any difference remains, and 2 when
OpenCode is not installed — a skip, since not having OpenCode is a legitimate way to
run the tracker.
"""

import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from collectors.opencode.locator import resolve_database_path  # noqa: E402
from config.settings import Settings, get_settings  # noqa: E402
from database.connection import create_database_engine, create_session_factory  # noqa: E402
from database.models import UsageEvent  # noqa: E402

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_NO_OPENCODE = 2


@dataclass
class ModelTotals:
    """One model's usage as each side reports it, plus how the two differ."""

    tokenly_messages: int = 0
    tokenly_input: int = 0
    tokenly_output: int = 0
    tokenly_reasoning: int = 0
    tokenly_cache_read: int = 0
    opencode_messages: int = 0
    opencode_input: int = 0
    opencode_output: int = 0
    opencode_reasoning: int = 0
    opencode_cache_read: int = 0
    unsynced: list[str] = field(default_factory=list)

    @property
    def incorrect(self) -> list[str]:
        """Token figures that disagree; any of these is a bug in Tokenly."""
        problems = []
        for label, ours, theirs in (
            ("input", self.tokenly_input, self.opencode_input),
            ("output", self.tokenly_output, self.opencode_output),
            ("reasoning", self.tokenly_reasoning, self.opencode_reasoning),
            ("cache read", self.tokenly_cache_read, self.opencode_cache_read),
        ):
            if ours != theirs:
                problems.append(f"{label}: tokenly={ours:,} opencode={theirs:,}")
        return problems


@dataclass
class OpenCodeSnapshot:
    """Everything read from OpenCode's own database."""

    totals: dict[str, ModelTotals]
    model_by_message: dict[str, str]
    still_generating: int


@dataclass
class TokenlySnapshot:
    """Everything read from Tokenly's database."""

    totals: dict[str, ModelTotals]
    message_ids: set[str]


def read_tokenly(settings: Settings) -> TokenlySnapshot:
    """Read stored usage grouped by model, plus which messages are stored."""
    engine = create_database_engine(settings.database_url)
    factory = create_session_factory(engine)
    totals: dict[str, ModelTotals] = defaultdict(ModelTotals)
    message_ids: set[str] = set()
    try:
        with factory() as session:
            rows = session.execute(
                select(
                    UsageEvent.model_id,
                    UsageEvent.source_event_id,
                    UsageEvent.input_tokens,
                    UsageEvent.output_tokens,
                    UsageEvent.reasoning_tokens,
                    UsageEvent.cache_read_tokens,
                )
            ).all()
        for model_id, event_id, input_tokens, output_tokens, reasoning, cache_read in rows:
            entry = totals[str(model_id)]
            entry.tokenly_messages += 1
            entry.tokenly_input += input_tokens or 0
            entry.tokenly_output += output_tokens or 0
            entry.tokenly_reasoning += reasoning or 0
            entry.tokenly_cache_read += cache_read or 0
            message_ids.add(str(event_id))
    finally:
        engine.dispose()
    return TokenlySnapshot(totals=dict(totals), message_ids=message_ids)


def read_opencode(source: Path) -> OpenCodeSnapshot:
    """Read OpenCode's own assistant-message usage, grouped by model.

    Opened `mode=ro` so validating can never modify the data it is checking. A message
    is counted only once it has completed: one still generating has no usage to compare
    and its absence from Tokenly is correct, not a discrepancy.
    """
    totals: dict[str, ModelTotals] = defaultdict(ModelTotals)
    model_by_message: dict[str, str] = {}
    still_generating = 0

    connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        cursor = connection.execute(
            "SELECT id, data FROM message WHERE json_extract(data, '$.role') = 'assistant'"
        )
        for message_id, raw in cursor:
            message = json.loads(raw)
            if (message.get("time") or {}).get("completed") is None:
                still_generating += 1
                continue
            payload = message.get("tokens")
            if not isinstance(payload, dict):
                continue

            model_id = str(message.get("modelID") or "unknown")
            model_by_message[str(message_id)] = model_id
            cache = payload.get("cache") or {}
            entry = totals[model_id]
            entry.opencode_messages += 1
            entry.opencode_input += payload.get("input") or 0
            entry.opencode_output += payload.get("output") or 0
            entry.opencode_reasoning += payload.get("reasoning") or 0
            entry.opencode_cache_read += cache.get("read") or 0
    finally:
        connection.close()

    return OpenCodeSnapshot(
        totals=dict(totals),
        model_by_message=model_by_message,
        still_generating=still_generating,
    )


def reconcile(ours: TokenlySnapshot, theirs: OpenCodeSnapshot) -> dict[str, ModelTotals]:
    """Merge both sides per model, recording wrong figures and unsynced messages.

    Each side is copied field by field rather than by merging two dictionaries: both
    entries carry the same field names, so a blanket merge would let the side missing a
    model's zero defaults silently overwrite the side holding real numbers — reporting
    every model as zero instead of raising.
    """
    missing_by_model = _unsynced_by_model(theirs, ours)

    merged: dict[str, ModelTotals] = {}
    for model_id in sorted(set(ours.totals) | set(theirs.totals)):
        mine = ours.totals.get(model_id, ModelTotals())
        upstream = theirs.totals.get(model_id, ModelTotals())
        merged[model_id] = ModelTotals(
            tokenly_messages=mine.tokenly_messages,
            tokenly_input=mine.tokenly_input,
            tokenly_output=mine.tokenly_output,
            tokenly_reasoning=mine.tokenly_reasoning,
            tokenly_cache_read=mine.tokenly_cache_read,
            opencode_messages=upstream.opencode_messages,
            opencode_input=upstream.opencode_input,
            opencode_output=upstream.opencode_output,
            opencode_reasoning=upstream.opencode_reasoning,
            opencode_cache_read=upstream.opencode_cache_read,
            unsynced=missing_by_model.get(model_id, []),
        )
    return merged


def _unsynced_by_model(theirs: OpenCodeSnapshot, ours: TokenlySnapshot) -> dict[str, list[str]]:
    """Return completed upstream messages Tokenly has not stored, grouped by model.

    Naming the messages makes a staleness report actionable: the ids can be looked up
    directly in OpenCode to see what has yet to be collected.
    """
    unsynced: dict[str, list[str]] = defaultdict(list)
    for message_id, model_id in theirs.model_by_message.items():
        if message_id not in ours.message_ids:
            unsynced[model_id].append(message_id)
    return dict(unsynced)


def report(merged: dict[str, ModelTotals], still_generating: int) -> tuple[bool, bool]:
    """Print the comparison; return whether figures are correct and fully synced."""
    print(f"{'model':38} {'messages':>9} {'input':>12} {'output':>10} {'reasoning':>10}")
    print("-" * 84)

    figures_ok = True
    synced = True
    for model_id, entry in merged.items():
        print(
            f"{model_id:38} {entry.tokenly_messages:>9,} {entry.tokenly_input:>12,} "
            f"{entry.tokenly_output:>10,} {entry.tokenly_reasoning:>10,}"
        )
        for problem in entry.incorrect:
            figures_ok = False
            print(f"    INCORRECT  {problem}")
        if entry.unsynced:
            synced = False
            print(
                f"    NOT SYNCED {len(entry.unsynced)} completed message(s) not stored; run a sync"
            )

    print()
    print("Note: `opencode stats` reports Output Tokens as output + reasoning.")
    print("      Tokenly keeps them separate because they are additive.")
    print(f"Ignored {still_generating} message(s) still generating upstream.")
    return figures_ok, synced


def main() -> int:
    """Validate Tokenly against OpenCode and return a process exit status."""
    settings = get_settings()
    source_path = resolve_database_path(settings)

    if not source_path.is_file():
        print(f"No OpenCode database at {source_path}; nothing to validate.")
        return EXIT_NO_OPENCODE

    ours = read_tokenly(settings)
    theirs = read_opencode(source_path)

    if not theirs.totals:
        print("OpenCode reported no completed usage; nothing to validate.")
        return EXIT_NO_OPENCODE

    figures_ok, synced = report(reconcile(ours, theirs), theirs.still_generating)
    print()
    if figures_ok and synced:
        print("Every model reconciles with OpenCode.")
        return EXIT_OK
    if not figures_ok:
        print("Token figures disagree with OpenCode.")
    if not synced:
        print("Some completed usage has not been collected yet.")
    return EXIT_MISMATCH


if __name__ == "__main__":
    raise SystemExit(main())
