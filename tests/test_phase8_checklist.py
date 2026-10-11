"""Phase 8 — the two requirements the rest of the suite only covered by accident.

Every item on the Phase 8 checklist is exercised somewhere. These are the two
that were implied rather than stated:

* **Free and paid models are tracked identically** (plan §4.4). A free-tier model
  must never be dropped, zeroed, or special-cased because its usage carries no
  cost. `test_multiple_models_in_one_session_stay_separate` happens to use one free
  and one paid model, but asserts only that they are attributed apart — it would
  still pass if the free one were stored as `unavailable`.

* **Both collectors use the same normalization** (Phase 3). The shared pipeline's
  promises — the total is input plus output, consumption adds the additive
  categories, a missing count is NULL rather than zero — are asserted for OpenCode
  and for Cline separately. What was never asserted is that identical usage data
  produces identical results from both, which is the actual claim.

Every other item on the Phase 8 checklist is already covered; §11 of
`implementation.md` points at where.

OpenCode and Cline store tokens differently on disk, so these tests deliberately
build each platform's own shape and compare what comes out.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collectors.cline import ClineCollector
from collectors.cline.extractor import extract_usage_record as cline_extract
from collectors.cline.reader import MessageRow as ClineMessageRow
from collectors.opencode.extractor import extract_usage_record as opencode_extract
from collectors.opencode.reader import MessageRow as OpenCodeMessageRow
from config.settings import Settings
from database.connection import Base
from database.repository import query_usage_events
from sync.service import SyncService
from tests.collectors.cline.conftest import ClineStoreBuilder

FIRST_MS = 1_790_495_317_187


def opencode_row(
    message_id: str,
    *,
    model: str = "big-pickle",
    tokens_payload: dict[str, object] | None = None,
) -> OpenCodeMessageRow:
    """An OpenCode assistant message row carrying the given token payload."""
    return OpenCodeMessageRow(
        message_id=message_id,
        session_id="ses_1",
        time_created_ms=FIRST_MS,
        data={
            "role": "assistant",
            "providerID": "opencode",
            "modelID": model,
            "tokens": tokens_payload
            or {
                "total": 610,
                "input": 500,
                "output": 110,
                "reasoning": 0,
                "cache": {"read": 0, "write": 0},
            },
            "time": {"created": FIRST_MS, "completed": FIRST_MS},
            "finish": "stop",
        },
    )


def cline_row(
    message_id: str,
    *,
    model: str = "cline-free/gemini-3.8-flash",
    metrics: dict[str, object] | None = None,
) -> ClineMessageRow:
    """A Cline assistant message row carrying the given token payload.

    `metrics={}` models the message Cline wrote with an empty metric object;
    `metrics=None` — the default — models an ordinary complete call.
    """
    payload = (
        {
            "inputTokens": 500,
            "outputTokens": 110,
            "cacheReadTokens": 0,
            "cacheWriteTokens": 0,
        }
        if metrics is None
        else metrics
    )
    return ClineMessageRow(
        message_id=message_id,
        session_id="ses_1",
        time_created_ms=FIRST_MS,
        data={
            "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
            "ts": FIRST_MS,
            "modelInfo": {"id": model, "provider": "cline"},
            "metrics": payload,
        },
    )


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A fresh Tokenly database factory for the test to store records into."""
    engine = create_engine(f"sqlite:///{tmp_path / 'tokenly.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


# --- free and paid models are treated alike ---


def test_a_free_model_is_stored_exactly_like_a_paid_one(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    store = ClineStoreBuilder(data_dir=tmp_path / "cline-data")
    store.add_assistant_message(
        {"modelInfo": {"id": "cline-free/gemini-3.8-flash", "provider": "cline"}},
        session_id="ses_free",
    )
    store.add_assistant_message(
        {"modelInfo": {"id": "stealth/space-bunny-alpha", "provider": "cline"}},
        session_id="ses_paid",
    )
    settings = Settings(cline_data_dir=store.data_dir, log_level="WARNING")

    with session_factory() as session:
        result = SyncService(ClineCollector(settings)).run(session)

    assert result.failed is False
    assert result.inserted == 2

    with session_factory() as session:
        rows = {row.model_id: row for row in query_usage_events(session, platform="cline")}

    free = rows["cline-free/gemini-3.8-flash"]
    paid = rows["stealth/space-bunny-alpha"]

    # Identical payloads in, identical treatment out — including the status. Only
    # the model name differs, so any other difference would be a free/paid special case.
    assert free.usage_status == paid.usage_status == "reported"
    assert free.input_tokens == paid.input_tokens == 100
    assert free.output_tokens == paid.output_tokens == 20
    assert free.total_tokens == paid.total_tokens == 120
    assert free.consumption_tokens == paid.consumption_tokens == 125


def test_a_free_model_with_no_reported_usage_is_unknown_not_zero() -> None:
    # The mirror case: a free-tier call Cline never reported a count for must be
    # `unavailable`, never a reported zero that would read as "this model was free".
    record = cline_extract(
        cline_row("msg_free_unknown", model="cline-free/muse-spark-1.3-contributor", metrics={})
    )

    assert record is not None
    assert record.model_id == "cline-free/muse-spark-1.3-contributor"
    assert record.usage_status == "unavailable"
    assert record.total_tokens is None


# --- the same normalization on both platforms ---


def test_identical_usage_normalizes_identically_on_both_platforms() -> None:
    # OpenCode stores a `tokens.total` and Cline stores no total at all; both must
    # arrive at the same numbers, because the total is computed rather than read.
    from_opencode = opencode_extract(
        opencode_row(
            "msg_oc",
            tokens_payload={
                "total": 999_999,
                "input": 500,
                "output": 110,
                "reasoning": 0,
                "cache": {"read": 0, "write": 0},
            },
        )
    )
    from_cline = cline_extract(cline_row("msg_cl"))

    assert from_opencode is not None
    assert from_cline is not None

    for field in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "consumption_tokens",
        "usage_status",
        "cache_overlap",
        "reasoning_overlap",
    ):
        assert getattr(from_opencode, field) == getattr(from_cline, field), field

    # The reported total from OpenCode's own field is deliberately ignored.
    assert from_opencode.total_tokens == 610


def test_a_reported_zero_is_data_on_one_platform_and_absence_on_the_other() -> None:
    # OpenCode writes a zeroed token block for an aborted call; Cline writes a
    # message with no metrics. Only Cline's is absence — the platform's own shape
    # decides, and the shared normaliser does not flatten that difference.
    opencode_zero = opencode_extract(
        opencode_row(
            "msg_oc_zero",
            tokens_payload={
                "total": 0,
                "input": 0,
                "output": 0,
                "reasoning": 0,
                "cache": {"read": 0, "write": 0},
            },
        )
    )
    cline_absent = cline_extract(cline_row("msg_cl_absent", metrics={}))

    assert opencode_zero is not None
    assert cline_absent is not None
    assert opencode_zero.usage_status == "reported"
    assert opencode_zero.total_tokens == 0
    assert cline_absent.usage_status == "unavailable"
    assert cline_absent.total_tokens is None


def test_cache_counts_the_same_way_on_both_platforms() -> None:
    from_opencode = opencode_extract(
        opencode_row(
            "msg_oc_cache",
            tokens_payload={
                "total": 650,
                "input": 500,
                "output": 110,
                "reasoning": 0,
                "cache": {"read": 40, "write": 0},
            },
        )
    )
    from_cline = cline_extract(
        cline_row(
            "msg_cl_cache",
            metrics={
                "inputTokens": 500,
                "outputTokens": 110,
                "cacheReadTokens": 40,
                "cacheWriteTokens": 0,
            },
        )
    )

    assert from_opencode is not None
    assert from_cline is not None
    # Cache sits outside the per-call total on both, and inside consumption on both.
    assert from_opencode.total_tokens == from_cline.total_tokens == 610
    assert from_opencode.consumption_tokens == from_cline.consumption_tokens == 650
    assert from_opencode.cache_read_tokens == from_cline.cache_read_tokens == 40

