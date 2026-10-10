"""Tests for the collector interface contract."""

from datetime import datetime, timezone

import pytest

from collectors.base import BaseCollector
from schemas.usage import DiscoveryResult, UsageRecord


class StubCollector(BaseCollector):
    """Minimal concrete collector used to verify the interface contract."""

    @property
    def platform(self) -> str:
        return "stub"

    def discover(self) -> DiscoveryResult:
        return DiscoveryResult(
            platform=self.platform,
            available=False,
            source_path="",
            storage_format="",
            detail="stub data source",
        )

    def collect_history(self) -> list[UsageRecord]:
        return []

    def collect_updates(self, checkpoint: str | None = None) -> list[UsageRecord]:
        return []


def test_collector_cannot_be_instantiated_without_an_implementation() -> None:
    with pytest.raises(TypeError):
        BaseCollector()  # type: ignore[abstract]


def test_stub_collector_reports_its_platform() -> None:
    assert StubCollector().platform == "stub"


def test_stub_collector_reports_nothing_available() -> None:
    collector = StubCollector()

    discovery = collector.discover()

    assert discovery.available is False
    assert collector.collect_history() == []
    assert collector.collect_updates() == []


def test_usage_record_normalizes_a_complete_call() -> None:
    record = UsageRecord(
        platform="stub",
        provider_id="example-provider",
        model_id="example-model",
        session_id="ses_1",
        message_id="msg_1",
        source_event_id="msg_1",
        timestamp=datetime(2026, 10, 11, tzinfo=timezone.utc),
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
    )

    assert record.usage_status == "reported"
    assert record.total_tokens == 150
