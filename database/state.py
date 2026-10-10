"""Persisting where each collector got to.

One row per platform, holding the checkpoint a scan should resume from. The checkpoint is
only advanced after a scan is fully stored, so an interrupted scan re-reads its window
rather than skipping past work it never saved. Phase 6 wires this into the sync loop;
this module is the storage it needs.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import CollectorState, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectorProgress:
    """What is stored for one collector between scans."""

    platform: str
    source_path: str
    checkpoint: str | None
    last_scan_at: datetime | None
    status: str


def load_progress(session: Session, platform: str) -> CollectorProgress | None:
    """Return a collector's stored progress, or None when it has never run."""
    state = session.execute(
        select(CollectorState).where(CollectorState.platform == platform)
    ).scalar_one_or_none()
    if state is None:
        logger.debug("no stored progress for platform %s", platform)
        return None
    return CollectorProgress(
        platform=state.platform,
        source_path=state.source_path,
        checkpoint=state.checkpoint,
        last_scan_at=state.last_scan_at,
        status=state.status,
    )


def save_progress(
    session: Session,
    platform: str,
    *,
    source_path: str = "",
    checkpoint: str | None = None,
    status: str = "idle",
    scanned_at: datetime | None = None,
) -> CollectorState:
    """Insert or update a collector's progress row and return it."""
    moment = scanned_at or utc_now()
    state = session.execute(
        select(CollectorState).where(CollectorState.platform == platform)
    ).scalar_one_or_none()

    if state is None:
        state = CollectorState(platform=platform)
        session.add(state)
        logger.debug("created collector state for %s", platform)

    state.source_path = source_path
    state.checkpoint = checkpoint
    state.status = status
    state.last_scan_at = moment
    session.commit()
    return state


def mark_scanning(session: Session, platform: str, source_path: str = "") -> None:
    """Record that a scan has started, so an unexpected stop is visible afterwards."""
    _save_status(session, platform, source_path, "scanning")


def mark_error(session: Session, platform: str, source_path: str = "") -> None:
    """Record that the last scan failed, leaving the checkpoint untouched for a retry.

    The checkpoint only advances after a scan's records are safely stored, so clearing
    it here would make a failed scan skip the window it never finished.
    """
    _save_status(session, platform, source_path, "error")
    logger.warning("collector %s recorded an error; checkpoint left unchanged", platform)


def _save_status(session: Session, platform: str, source_path: str, status: str) -> None:
    """Change only the status, keeping the checkpoint and source path already stored."""
    progress = load_progress(session, platform)
    save_progress(
        session,
        platform,
        source_path=source_path or (progress.source_path if progress else ""),
        checkpoint=progress.checkpoint if progress else None,
        status=status,
    )


def checkpoint_for(session: Session, platform: str) -> str | None:
    """Return just the stored checkpoint for a platform, or None."""
    progress = load_progress(session, platform)
    return None if progress is None else progress.checkpoint
