"""Building usage records for API tests.

Every test that asks an endpoint a question about usage needs rows to ask it about.
Seeding goes through the real `upsert_usage_records` path so the database holds what a
collector would have written, not a hand-built approximation of it.
"""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI

from database.repository import upsert_usage_records
from schemas.usage import UsageRecord


def make_record(
    event_id: str,
    timestamp: datetime,
    *,
    platform: str = "opencode",
    provider_id: str = "openrouter",
    model_id: str = "example-model",
    input_tokens: int | None = 100,
    output_tokens: int | None = 20,
    consumption_tokens: int | None = 120,
    session_id: str = "ses_1",
) -> UsageRecord:
    """One normalized record standing in for a stored model call."""
    total = None if input_tokens is None or output_tokens is None else input_tokens + output_tokens
    return UsageRecord(
        platform=platform,
        provider_id=provider_id,
        model_id=model_id,
        session_id=session_id,
        message_id=event_id,
        source_event_id=event_id,
        timestamp=timestamp,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total,
        consumption_tokens=consumption_tokens,
        usage_status="reported",
    )


def seed(app: FastAPI, records: Iterable[UsageRecord]) -> None:
    """Store records through the real upsert path, using the app's own session."""
    session_factory = app.state.session_factory
    with session_factory() as session:
        upsert_usage_records(session, list(records))


def body(response: httpx.Response) -> dict[str, Any]:
    """Return a response's JSON body, typed for test assertions."""
    payload: dict[str, Any] = response.json()
    return payload


def totals_of(response: httpx.Response) -> dict[str, int]:
    """Return the token totals from a summary or timeline response."""
    totals: dict[str, int] = body(response)["totals"]
    return totals


def rescan_runs(response: httpx.Response) -> Sequence[dict[str, Any]]:
    """Return the per-collector runs from a rescan response."""
    runs: list[dict[str, Any]] = response.json()
    return runs


def first_run(response: httpx.Response) -> dict[str, Any]:
    """Return the first of a rescan response's runs."""
    return rescan_runs(response)[0]


def collectors_of(response: httpx.Response) -> Sequence[dict[str, Any]]:
    """Return the collector entries from a status response."""
    entries: list[dict[str, Any]] = body(response)["collectors"]
    return entries


def bucket_labels(response: httpx.Response) -> Sequence[str]:
    """Return the labels of a timeline's buckets, in order."""
    labels: list[str] = [bucket["label"] for bucket in body(response)["buckets"]]
    return labels
