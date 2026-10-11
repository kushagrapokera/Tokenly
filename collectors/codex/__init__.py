"""Codex CLI collector package: the only place that knows Codex's storage layout.

The rollout JSONL layout lives in `.reader`; every other Tokenly module sees only
the normalized `UsageRecord` this package produces. Layout changes break the
learning tests in `tests/collectors/codex/` instead of silently skewing totals.
"""

from collectors.codex.collector import CodexCollector

__all__ = ["CodexCollector"]
