"""Tests for synchronization: the guarantee that rescans never inflate totals."""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from collectors.base import BaseCollector, ScanOutcome
from collectors.checkpoint import Checkpoint
from collectors.opencode import OpenCodeCollector
from database.connection import Base
from database.repository import count_usage_events, query_usage_events, sum_tokens
from database.state import load_progress
from schemas.usage import DiscoveryResult, UsageRecord
from sync import MODE_HISTORICAL, MODE_INCREMENTAL, SyncService
from sync.result import SyncResult

UTC = timezone.utc
FIRST_MS = 1_700_000_000_000
SECOND_MS = FIRST_MS + 60_000


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as open_session:
        yield open_session
    engine.dispose()


def make_record(event_id: str, timestamp_ms: int, consumption: int = 100) -> UsageRecord:
    """A record standing in for one stored model call."""
    return UsageRecord(
        platform="opencode",
        provider_id="opencode",
        model_id="space-bunny-free",
        session_id="ses_1",
        message_id=event_id,
        source_event_id=event_id,
        timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC),
        input_tokens=consumption - 10,
        output_tokens=10,
        total_tokens=consumption,
        consumption_tokens=consumption,
        usage_status="reported",
    )


class FakeCollector(BaseCollector):
    """A collector backed by a list the test controls, including unfinished messages."""

    def __init__(self, records: list[UsageRecord], pending: list[int] | None = None) -> None:
        self.records = records
        self.pending = pending or []
        self.reads: list[str | None] = []

    @property
    def platform(self) -> str:
        return "opencode"

    def discover(self) -> DiscoveryResult:
        return DiscoveryResult(
            platform=self.platform,
            available=True,
            source_path="/fake/opencode.db",
            storage_format="sqlite",
        )

    def collect_history(self) -> list[UsageRecord]:
        return list(self.records)

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        self.reads.append(checkpoint)
        return list(self.records)

    def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
        self.reads.append(checkpoint)
        return ScanOutcome(records=list(self.records), pending_timestamps_ms=list(self.pending))


# --- the core guarantee ---


def test_the_first_run_imports_everything(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", FIRST_MS), make_record("msg_2", SECOND_MS)])

    result = SyncService(collector).run(session)

    assert result.mode == MODE_HISTORICAL
    assert result.inserted == 2
    assert count_usage_events(session) == 2


def test_running_sync_twice_does_not_inflate_the_total(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", FIRST_MS), make_record("msg_2", SECOND_MS)])
    service = SyncService(collector)

    service.run(session)
    second = service.run(session)

    assert (second.inserted, second.updated) == (0, 2)
    assert count_usage_events(session) == 2
    assert sum_tokens(session, "consumption_tokens") == 200


def test_running_sync_many_times_keeps_the_total_flat(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", FIRST_MS)])
    service = SyncService(collector)

    for _ in range(10):
        service.run(session)

    assert sum_tokens(session, "consumption_tokens") == 100


def test_a_restart_mid_history_does_not_double_count(session: Session) -> None:
    """A fresh service with no checkpoint re-reads everything; upsert absorbs it."""
    records = [make_record(f"msg_{i}", FIRST_MS + i) for i in range(5)]
    SyncService(FakeCollector(records)).run(session)

    result = SyncService(FakeCollector(records)).run(session)

    assert result.inserted == 0
    assert count_usage_events(session) == 5


# --- checkpoints ---


def test_the_checkpoint_advances_after_a_successful_scan(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", SECOND_MS)])

    result = SyncService(collector).run(session)

    assert result.checkpoint == str(SECOND_MS)


def test_the_next_scan_resumes_from_the_stored_checkpoint(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", SECOND_MS)])
    service = SyncService(collector)
    service.run(session)

    service.run(session)

    assert collector.reads[-1] == str(SECOND_MS)


def test_a_scan_that_finds_nothing_keeps_the_previous_checkpoint(session: Session) -> None:
    service = SyncService(FakeCollector([make_record("msg_1", SECOND_MS)]))
    first = service.run(session)

    empty = SyncService(FakeCollector([])).run(session)

    assert empty.checkpoint == first.checkpoint


def test_the_rescan_overlap_reads_slightly_further_back(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", SECOND_MS)])
    service = SyncService(collector, rescan_overlap_ms=5_000)
    service.run(session)

    service.run(session)

    assert collector.reads[-1] == str(SECOND_MS - 5_000)


# --- streaming partial usage ---


def test_a_message_still_generating_holds_the_checkpoint_back(session: Session) -> None:
    """Advancing past an unfinished message would skip its usage forever."""
    collector = FakeCollector([make_record("msg_done", SECOND_MS)], pending=[FIRST_MS])

    result = SyncService(collector).run(session)

    assert result.skipped_in_flight == 1
    assert result.checkpoint == str(FIRST_MS - 1)


def test_a_message_finishing_later_is_picked_up_on_the_next_scan(session: Session) -> None:
    pending_collector = FakeCollector([make_record("msg_done", SECOND_MS)], pending=[FIRST_MS])
    service = SyncService(pending_collector)
    service.run(session)

    # The message finishes and now carries usage.
    finished = FakeCollector(
        [make_record("msg_done", SECOND_MS), make_record("msg_late", FIRST_MS)]
    )
    result = SyncService(finished).run(session)

    assert result.inserted == 1
    assert count_usage_events(session) == 2


def test_a_pending_message_newer_than_the_records_does_not_rewind_the_checkpoint(
    session: Session,
) -> None:
    collector = FakeCollector([make_record("msg_1", FIRST_MS)], pending=[SECOND_MS])

    result = SyncService(collector).run(session)

    assert result.checkpoint == str(FIRST_MS)


# --- failure recovery ---


def test_a_failed_scan_records_the_error_and_leaves_the_checkpoint(session: Session) -> None:
    service = SyncService(FakeCollector([make_record("msg_1", FIRST_MS)]))
    service.run(session)

    class BrokenCollector(FakeCollector):
        def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
            raise RuntimeError("source unavailable")

    result = SyncService(BrokenCollector([])).run(session)

    assert result.failed is True
    assert "source unavailable" in result.error_message
    progress = load_progress(session, "opencode")
    assert progress is not None
    assert progress.status == "error"
    assert progress.checkpoint == str(FIRST_MS)


def test_a_scan_interrupted_before_finishing_is_detected_on_restart(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """A scan killed mid-flight leaves status 'scanning'; the retry says so."""
    from database.state import mark_scanning

    mark_scanning(session, "opencode")

    SyncService(FakeCollector([make_record("msg_1", FIRST_MS)])).run(session)

    assert "did not finish" in caplog.text


def test_a_failed_scan_does_not_lose_records_stored_before_it(session: Session) -> None:
    service = SyncService(FakeCollector([make_record("msg_1", FIRST_MS)]))
    service.run(session)

    class BrokenCollector(FakeCollector):
        def collect_scan(self, checkpoint: str | None = None) -> ScanOutcome:
            raise RuntimeError("boom")

    SyncService(BrokenCollector([])).run(session)

    assert count_usage_events(session) == 1
    assert sum_tokens(session, "consumption_tokens") == 100


# --- retries and compaction ---


def test_a_retried_message_updates_its_row_instead_of_adding_one(session: Session) -> None:
    SyncService(FakeCollector([make_record("msg_1", FIRST_MS, consumption=100)])).run(session)

    result = SyncService(FakeCollector([make_record("msg_1", FIRST_MS, consumption=250)])).run(
        session
    )

    assert result.updated == 1
    assert count_usage_events(session) == 1
    assert sum_tokens(session, "consumption_tokens") == 250


def test_usage_survives_the_source_emptying_out(session: Session) -> None:
    """Session compaction removes source rows; stored usage must remain."""
    SyncService(FakeCollector([make_record("msg_1", FIRST_MS)])).run(session)

    SyncService(FakeCollector([])).run(session)

    assert count_usage_events(session) == 1
    assert sum_tokens(session, "consumption_tokens") == 100


def test_a_source_row_that_reappears_does_not_duplicate(session: Session) -> None:
    records = [make_record("msg_1", FIRST_MS)]
    SyncService(FakeCollector(records)).run(session)

    for _ in range(3):
        SyncService(FakeCollector(records)).run(session)

    assert count_usage_events(session) == 1


# --- result reporting ---


def test_the_result_reports_what_happened(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", FIRST_MS)])

    result: SyncResult = SyncService(collector).run(session)

    assert result.platform == "opencode"
    assert result.scanned == 1
    assert result.stored == 1
    assert result.succeeded is True
    assert result.duration_seconds >= 0


def test_the_second_run_is_reported_as_incremental(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", FIRST_MS)])
    service = SyncService(collector)
    service.run(session)

    assert service.run(session).mode == MODE_INCREMENTAL


# --- against the real collector ---


def test_real_records_sync_without_duplication(session: Session) -> None:
    collector = OpenCodeCollector()
    if not collector.discover().available:
        pytest.skip("no OpenCode database on this machine")
    records = collector.collect_history()[:150]
    if not records:
        pytest.skip("no completed assistant messages to import")

    first = SyncService(FakeCollector(records)).run(session)
    second = SyncService(FakeCollector(records)).run(session)
    total = sum_tokens(session, "consumption_tokens")

    assert first.inserted == len(records)
    assert second.inserted == 0
    assert count_usage_events(session) == len(records)
    assert total == sum(r.consumption_tokens or 0 for r in records)


def test_a_restart_mid_sync_does_not_duplicate_real_records(session: Session) -> None:
    collector = OpenCodeCollector()
    if not collector.discover().available:
        pytest.skip("no OpenCode database on this machine")
    records = collector.collect_history()[:100]
    if not records:
        pytest.skip("no completed assistant messages to import")

    SyncService(FakeCollector(records)).run(session)
    result = SyncService(FakeCollector(records)).run(session)

    assert result.inserted == 0
    assert count_usage_events(session) == len(records)


def test_the_real_collector_reports_in_flight_messages(session: Session) -> None:
    collector = OpenCodeCollector()
    if not collector.discover().available:
        pytest.skip("no OpenCode database on this machine")

    outcome = collector.collect_scan(None)

    assert outcome.records
    assert outcome.latest_timestamp_ms is not None
    # A message can be created after the newest completed one; that is exactly the
    # in-flight case, and it is why the checkpoint guard exists.
    for pending_ms in outcome.pending_timestamps_ms:
        assert isinstance(pending_ms, int)
        assert pending_ms > 0


def test_the_stored_checkpoint_is_parseable(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", FIRST_MS)])

    result = SyncService(collector).run(session)

    parsed = Checkpoint.parse(result.checkpoint)
    assert parsed is not None
    assert parsed.last_seen_ms == FIRST_MS


def test_stored_timestamps_can_be_queried_by_range(session: Session) -> None:
    SyncService(
        FakeCollector([make_record("msg_1", FIRST_MS), make_record("msg_2", SECOND_MS)])
    ).run(session)

    found = query_usage_events(session, start=datetime.fromtimestamp(FIRST_MS / 1000, tz=UTC))

    assert len(found) == 2


def test_a_clock_can_be_injected_for_deterministic_timing(session: Session) -> None:
    steps = iter(FIRST_MS + offset for offset in (0, 250, 500, 750, 1000))
    clock = lambda: datetime.fromtimestamp(next(steps) / 1000, tz=UTC)  # noqa: E731

    result = SyncService(FakeCollector([make_record("msg_1", FIRST_MS)]), clock=clock).run(session)

    assert result.started_at == datetime.fromtimestamp(FIRST_MS / 1000, tz=UTC)
    assert result.finished_at > result.started_at


def test_the_rescan_overlap_is_off_by_default(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", SECOND_MS)])
    service = SyncService(collector)
    service.run(session)

    service.run(session)

    assert collector.reads[-1] == str(SECOND_MS)


def test_a_scan_reports_no_in_flight_messages_when_all_are_done(session: Session) -> None:
    result = SyncService(FakeCollector([make_record("msg_1", FIRST_MS)])).run(session)

    assert result.skipped_in_flight == 0


def test_a_zero_overlap_does_not_change_the_resume_point(session: Session) -> None:
    collector = FakeCollector([make_record("msg_1", SECOND_MS)])
    service = SyncService(collector, rescan_overlap_ms=0)
    service.run(session)

    service.run(session)

    assert collector.reads[-1] == str(SECOND_MS)


def test_a_run_with_no_records_reports_zero_scanned(session: Session) -> None:
    result = SyncService(FakeCollector([])).run(session)

    assert result.scanned == 0
    assert result.stored == 0
    assert result.succeeded is True


def test_two_platforms_keep_independent_checkpoints(session: Session) -> None:
    class OtherCollector(FakeCollector):
        @property
        def platform(self) -> str:
            return "claude"

    SyncService(FakeCollector([make_record("msg_1", FIRST_MS)])).run(session)
    SyncService(OtherCollector([make_record("msg_c", SECOND_MS)])).run(session)

    opencode_progress = load_progress(session, "opencode")
    claude_progress = load_progress(session, "claude")
    assert opencode_progress is not None
    assert claude_progress is not None
    assert opencode_progress.checkpoint == str(FIRST_MS)
    assert claude_progress.checkpoint == str(SECOND_MS)


def test_the_rescan_overlap_catches_a_message_that_finished_late(session: Session) -> None:
    """With an overlap, a message finishing after the scan still gets collected."""
    collector = FakeCollector([make_record("msg_done", SECOND_MS)])
    service = SyncService(collector, rescan_overlap_ms=60_000)
    service.run(session)

    late = FakeCollector([make_record("msg_done", SECOND_MS), make_record("msg_late", FIRST_MS)])
    result = SyncService(late, rescan_overlap_ms=60_000).run(session)

    assert result.inserted == 1
    assert count_usage_events(session) == 2


def test_records_arrive_in_a_stable_order(session: Session) -> None:
    records = [make_record("msg_2", SECOND_MS), make_record("msg_1", FIRST_MS)]

    SyncService(FakeCollector(records)).run(session)

    stored = query_usage_events(session)
    assert [row.source_event_id for row in stored] == ["msg_1", "msg_2"]


def test_the_stored_total_matches_the_collector_exactly(session: Session) -> None:
    records = [make_record("msg_1", FIRST_MS, 100), make_record("msg_2", SECOND_MS, 250)]

    SyncService(FakeCollector(records)).run(session)

    assert sum_tokens(session, "consumption_tokens") == 350
    assert sum_tokens(session, "input_tokens") == (90 + 240)


def test_the_service_can_be_reused_across_runs(session: Session) -> None:
    service = SyncService(FakeCollector([make_record("msg_1", FIRST_MS)]))

    first = service.run(session)
    second = service.run(session)

    assert first.succeeded and second.succeeded
    assert second.inserted == 0
    assert second.updated == 1
    assert count_usage_events(session) == 1


def test_a_scan_after_a_manual_checkpoint_reset_reimports_safely(session: Session) -> None:
    records = [make_record("msg_1", FIRST_MS)]
    SyncService(FakeCollector(records)).run(session)

    from database.state import save_progress

    save_progress(session, "opencode", checkpoint=None)
    result = SyncService(FakeCollector(records)).run(session)

    assert result.mode == MODE_HISTORICAL
    assert result.inserted == 0
    assert count_usage_events(session) == 1
