"""Keeping the database current without anyone asking.

A local tracker that only updates when a button is pressed is a tracker whose
numbers are wrong. This module runs the coordinator once at startup — so a fresh
install imports whatever history already exists — and then again on an interval,
so usage lands in the dashboard while the user works.

Two details keep it well behaved:

* Scans run in a worker thread. `SyncService` is blocking, and a cold OpenCode
  history can take seconds; running it inline would freeze every API request for
  the duration.
* Shutdown is cooperative. `run_periodically` waits on an event rather than
  sleeping, so closing the application does not wait out the remaining interval
  and does not start one more scan on the way out.
"""

import asyncio
import logging

from sync.coordinator import SessionFactory, SyncCoordinator

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Runs the coordinator at startup and then on a fixed interval."""

    def __init__(
        self,
        coordinator: SyncCoordinator,
        session_factory: SessionFactory,
        interval_seconds: float,
    ) -> None:
        self._coordinator = coordinator
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds

    @property
    def interval_seconds(self) -> float:
        """How long the scheduler waits between passes."""
        return self._interval_seconds

    @property
    def platforms(self) -> list[str]:
        """The platforms this scheduler scans."""
        return self._coordinator.platforms

    async def run_periodically(self, stop: asyncio.Event) -> None:
        """Scan now, then every interval, until asked to stop."""
        await self.run_once()
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._interval_seconds)
            except TimeoutError:
                logger.debug("sync interval elapsed; scanning again")
            if stop.is_set():
                logger.info("sync scheduler stopping")
                return
            await self.run_once()

    async def run_once(self) -> None:
        """Run one full pass off the event loop, logging whatever it did.

        Failures are the coordinator's to handle; this only guards the scheduler
        itself, so an unexpected error ends the pass instead of killing the loop.
        """
        try:
            await asyncio.to_thread(self._scan)
        except Exception:  # noqa: BLE001 - the loop must outlive a bad pass
            logger.exception("a sync pass failed; the scheduler will try again")

    def _scan(self) -> None:
        """Run every collector once. Blocks; called in a worker thread."""
        logger.info("starting a sync pass over %s", self._coordinator.platforms)
        results = self._coordinator.run_all(self._session_factory)
        stored = sum(result.stored for result in results)
        logger.info("sync pass finished: %d record(s) stored", stored)