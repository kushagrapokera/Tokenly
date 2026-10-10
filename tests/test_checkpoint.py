"""Tests for incremental-scan checkpoints."""

from datetime import datetime, timezone

import pytest

from collectors.checkpoint import Checkpoint, InvalidCheckpointError


def test_no_stored_checkpoint_means_start_from_the_beginning() -> None:
    assert Checkpoint.parse(None) is None
    assert Checkpoint.parse("") is None


def test_a_checkpoint_survives_a_write_and_read_cycle() -> None:
    original = Checkpoint(last_seen_ms=1_789_532_819_792)

    restored = Checkpoint.parse(original.serialize())

    assert restored == original


def test_a_non_numeric_checkpoint_is_rejected_with_context() -> None:
    with pytest.raises(InvalidCheckpointError) as caught:
        Checkpoint.parse("yesterday")

    assert "yesterday" in str(caught.value)


def test_messages_older_than_the_checkpoint_are_covered() -> None:
    checkpoint = Checkpoint(last_seen_ms=1_000)

    assert checkpoint.covers(999) is True
    assert checkpoint.covers(1_000) is False
    assert checkpoint.covers(1_001) is False


def test_the_checkpoints_own_millisecond_is_re_read_on_purpose() -> None:
    """A message written in that millisecond may only now have finished generating."""
    checkpoint = Checkpoint(last_seen_ms=1_000)

    assert checkpoint.covers(1_000) is False


def test_a_checkpoint_can_be_built_from_an_aware_datetime() -> None:
    moment = datetime(2026, 9, 16, 4, 26, 59, 792000, tzinfo=timezone.utc)

    assert Checkpoint.from_datetime(moment).last_seen_ms == 1_789_532_819_792


def test_a_checkpoint_converts_back_to_the_same_utc_datetime() -> None:
    moment = datetime(2026, 9, 16, 4, 26, 59, 792000, tzinfo=timezone.utc)

    assert Checkpoint.from_datetime(moment).to_datetime() == moment
