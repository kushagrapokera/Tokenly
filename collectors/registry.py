"""The collectors this build knows how to run.

Registration lives here so adding a platform means adding one line in one file, and so
the API can enumerate what it can collect without importing platform code itself.
"""

import logging

from collectors.base import BaseCollector
from collectors.claude import ClaudeCodeCollector
from collectors.cline import ClineCollector
from collectors.codex import CodexCollector
from collectors.opencode import OpenCodeCollector
from config.settings import Settings

logger = logging.getLogger(__name__)


def build_collectors(settings: Settings) -> list[BaseCollector]:
    """Return one collector per supported platform, in the order they should run."""
    collectors: list[BaseCollector] = [
        OpenCodeCollector(settings),
        ClineCollector(settings),
        ClaudeCodeCollector(settings),
        CodexCollector(settings),
    ]
    logger.info(
        "registered %d collector(s): %s",
        len(collectors),
        ", ".join(collector.platform for collector in collectors),
    )
    return collectors


__all__ = ["build_collectors"]
