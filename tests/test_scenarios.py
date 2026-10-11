"""Scenario tests: the full pipeline against a stand-in OpenCode database.

Each test names a situation a user can actually be in — a paid model, a request that
died mid-flight, a session compacted out from under us — and asserts on the totals a
dashboard would show afterwards. Where the correct answer is subtle (an interrupted
request should count as zero, not as missing; a retry should not add a second row),
the test states that expectation in its name so a failure explains itself.

Nothing here reaches into Tokenly's database to arrange a state. Scenarios are produced
by writing, updating, or deleting rows in the *source*, exactly as OpenCode does.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.scenarios import (
    BASE_MS,
    MINUTE_MS,
    ScenarioEnvironment,
    StoredMessage,
    make_scenario,
    tokens,
    totals_of,
)


@pytest.fixture
def scenario(tmp_path: Path) -> Iterator[ScenarioEnvironment]:
    """A fake OpenCode source plus a Tokenly database."""
    yield from make_scenario(tmp_path)


# --- Session and model shapes -------------------------------------------------


def test_a_single_session_with_one_model_is_counted_once(scenario: ScenarioEnvironment) -> None:
    scenario.write([StoredMessage("msg_1", tokens=tokens(100, 20))])

    result = scenario.sync()

    assert result.inserted == 1
    summary = scenario.summary()
    assert (summary.request_count, summary.total_tokens) == (1, 120)


def test_multiple_sessions_with_one_model_keep_their_own_identity(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_1", session_id="ses_a", created_ms=BASE_MS, tokens=tokens(100, 20)),
            StoredMessage(
                "msg_2",
                session_id="ses_b",
                created_ms=BASE_MS + MINUTE_MS,
                tokens=tokens(50, 5),
            ),
        ]
    )

    scenario.sync()

    summary = scenario.summary()
    assert summary.request_count == 2
    assert summary.total_tokens == 175


def test_multiple_models_in_one_session_are_attributed_separately(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_1", model_id="model-a", tokens=tokens(100, 20)),
            StoredMessage("msg_2", model_id="model-b", created_ms=BASE_MS + 1, tokens=tokens(7, 3)),
        ]
    )

    scenario.sync()

    pairs = {(model.provider_id, model.model_id): model.total_tokens for model in scenario.models()}
    assert pairs == {("opencode", "model-a"): 120, ("opencode", "model-b"): 10}


def test_two_providers_serving_the_same_model_name_stay_distinct(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage(
                "msg_1", provider_id="opencode", model_id="sonnet", tokens=tokens(100, 20)
            ),
            StoredMessage(
                "msg_2",
                provider_id="anthropic",
                model_id="sonnet",
                created_ms=BASE_MS + 1,
                tokens=tokens(9, 1),
            ),
        ]
    )

    scenario.sync()

    pairs = {(model.provider_id, model.model_id) for model in scenario.models()}
    assert pairs == {("opencode", "sonnet"), ("anthropic", "sonnet")}


# --- Model cost classes -------------------------------------------------------


def test_a_free_hosted_model_is_tracked_the_same_as_a_paid_one(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_free", model_id="free-hosted", tokens=tokens(100, 20)),
            StoredMessage(
                "msg_paid",
                model_id="paid-api",
                created_ms=BASE_MS + 1,
                tokens=tokens(300, 60),
            ),
        ]
    )

    scenario.sync()

    summary = scenario.summary()
    assert summary.request_count == 2
    # A free model is not special-cased: it is tracked on the same terms as a paid one.
    assert summary.total_tokens == 480


def test_a_local_model_reports_usage_and_is_tracked(scenario: ScenarioEnvironment) -> None:
    scenario.write(
        [StoredMessage("msg_1", provider_id="ollama", model_id="llama3", tokens=tokens(11, 2))]
    )

    scenario.sync()

    summary = scenario.summary()
    assert (summary.request_count, summary.total_tokens) == (1, 13)
    assert scenario.models()[0].provider_id == "ollama"


def test_reasoning_and_cache_tokens_are_tracked_but_do_not_inflate_the_total(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage(
                "msg_1",
                tokens=tokens(100, 20, reasoning=300, cache_read=5_000),
            )
        ]
    )

    scenario.sync()

    summary = scenario.summary()
    # OpenCode's own total for this call is input+output+reasoning+cache = 5,420.
    assert summary.total_tokens == 120
    assert summary.consumption_tokens == 5_420


# --- Interrupted, streaming, and retried requests ------------------------------


def test_a_request_interrupted_before_finishing_counts_as_zero_not_missing(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_ok", tokens=tokens(100, 20)),
            StoredMessage(
                "msg_aborted",
                created_ms=BASE_MS + 1,
                tokens=tokens(0, 0),
                finish="abort",
            ),
        ]
    )

    scenario.sync()

    summary = scenario.summary()
    assert summary.request_count == 2
    assert summary.total_tokens == 120
    assert summary.unknown_total_events == 0


def test_a_streaming_request_is_picked_up_when_it_finishes(scenario: ScenarioEnvironment) -> None:
    # OpenCode writes the message row when generation starts, before it has finished.
    scenario.write([StoredMessage("msg_stream", tokens=None, finish=None, completed=False)])

    first = scenario.sync()
    assert first.inserted == 0
    assert first.skipped_in_flight == 1
    assert scenario.stored_events() == 0

    # The call finishes and OpenCode backfills the same row.
    scenario.write_message(StoredMessage("msg_stream", tokens=tokens(64, 8), completed=True))

    second = scenario.sync()
    assert second.inserted == 1
    assert scenario.summary().total_tokens == 72


def test_a_message_that_finished_without_reporting_usage_is_recorded_as_unavailable(
    scenario: ScenarioEnvironment,
) -> None:
    # Completed, but the source never reported counts: unavailable, not zero and not missing.
    scenario.write([StoredMessage("msg_done", tokens=None, completed=True)])

    result = scenario.sync()

    assert result.inserted == 1
    summary = scenario.summary()
    assert summary.request_count == 1
    assert summary.unknown_total_events == 1
    assert summary.total_tokens == 0


def test_a_retried_request_updates_its_row_rather_than_adding_one(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write([StoredMessage("msg_1", tokens=tokens(100, 20))])
    scenario.sync()
    assert scenario.summary().total_tokens == 120

    # The retry lands on the same message id with the real usage.
    scenario.write_message(StoredMessage("msg_1", tokens=tokens(150, 30)))

    result = scenario.sync()

    assert (result.inserted, result.updated) == (0, 1)
    assert scenario.stored_events() == 1
    assert scenario.summary().total_tokens == 180


def test_a_message_still_generating_holds_the_checkpoint_back(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_done", created_ms=BASE_MS, tokens=tokens(100, 20)),
            StoredMessage(
                "msg_slow",
                created_ms=BASE_MS + MINUTE_MS,
                tokens=None,
                finish=None,
                completed=False,
            ),
        ]
    )

    scenario.sync()

    progress = scenario.progress()
    assert progress is not None
    # The checkpoint must not pass the unfinished message, or its usage would be skipped.
    assert progress.checkpoint is not None
    assert int(progress.checkpoint) < BASE_MS + MINUTE_MS


# --- History that changes underneath us ----------------------------------------


def test_compacting_a_session_does_not_remove_stored_usage(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write([StoredMessage("msg_1", session_id="ses_old", tokens=tokens(100, 20))])
    scenario.sync()
    assert scenario.summary().total_tokens == 120

    scenario.compact_session("ses_old")

    result = scenario.sync(from_scratch=True)

    assert result.inserted == 0
    assert scenario.stored_events() == 1
    assert scenario.summary().total_tokens == 120


def test_deleting_the_entire_source_leaves_stored_usage_intact(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write([StoredMessage("msg_1", tokens=tokens(100, 20))])
    scenario.sync()

    scenario.compact_session("ses_0001")
    scenario.sync(from_scratch=True)

    assert scenario.stored_events() == 1
    assert scenario.summary().total_tokens == 120


def test_historical_import_reads_everything_on_the_first_run(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage(
                f"msg_{index}",
                created_ms=BASE_MS + index * MINUTE_MS,
                tokens=tokens(10, 1),
            )
            for index in range(25)
        ]
    )

    result = scenario.sync()

    assert result.mode == "historical"
    assert result.inserted == 25
    assert scenario.summary().total_tokens == 25 * 11


def test_new_usage_after_the_first_import_is_collected_incrementally(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write([StoredMessage("msg_1", tokens=tokens(100, 20))])
    first = scenario.sync()
    assert first.mode == "historical"

    scenario.write_message(
        StoredMessage("msg_2", created_ms=BASE_MS + MINUTE_MS, tokens=tokens(50, 5))
    )

    second = scenario.sync()

    assert second.mode == "incremental"
    assert second.inserted == 1
    assert scenario.summary().total_tokens == 175


def test_usage_survives_an_application_restart(scenario: ScenarioEnvironment) -> None:
    scenario.write([StoredMessage("msg_1", tokens=tokens(100, 20))])
    scenario.sync()
    before = scenario.summary()

    scenario.restart()
    scenario.sync()
    after = scenario.summary()

    assert after.total_tokens == before.total_tokens
    assert after.request_count == before.request_count


def test_repeated_runs_and_restarts_never_inflate_a_total(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_1", tokens=tokens(100, 20)),
            StoredMessage("msg_2", created_ms=BASE_MS + MINUTE_MS, tokens=tokens(50, 5)),
        ]
    )
    scenario.sync()
    expected = scenario.summary()

    for _ in range(3):
        scenario.sync()
        scenario.restart()
        scenario.sync(from_scratch=True)

    final = scenario.summary()
    assert totals_of(final) == totals_of(expected)
    assert final.request_count == expected.request_count


# --- Missing usage ------------------------------------------------------------


def test_a_message_that_never_reported_usage_is_visible_as_incomplete(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_known", tokens=tokens(100, 20)),
            StoredMessage("msg_unknown", created_ms=BASE_MS + 1, tokens={}),
        ]
    )

    scenario.sync()

    summary = scenario.summary()
    assert summary.request_count == 2
    assert summary.known_total_events == 1
    assert summary.unknown_total_events == 1
    assert summary.total_tokens == 120


def test_a_missing_usage_message_does_not_zero_out_a_real_total(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_1", tokens=tokens(100, 20)),
            StoredMessage("msg_2", created_ms=BASE_MS + 1, tokens={"input": None, "output": None}),
        ]
    )

    scenario.sync()

    summary = scenario.summary()
    assert summary.total_tokens == 120
    assert summary.unknown_total_events == 1


def test_a_corrupt_source_row_is_skipped_without_losing_the_rest(
    scenario: ScenarioEnvironment,
) -> None:
    scenario.write(
        [
            StoredMessage("msg_ok", tokens=tokens(100, 20)),
            StoredMessage("msg_bad", created_ms=BASE_MS + 1),
        ]
    )
    scenario.write_message(StoredMessage("msg_bad", created_ms=BASE_MS + 1))
    import sqlite3

    with sqlite3.connect(scenario.source_path) as connection:
        connection.execute(
            "UPDATE message SET data = ? WHERE id = ?", ("{not valid json", "msg_bad")
        )

    scenario.sync()

    assert scenario.summary().total_tokens == 120
