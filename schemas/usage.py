"""Normalized usage record shared by every collector."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

UsageStatus = Literal["reported", "estimated", "unavailable"]


class UsageRecord(BaseModel):
    """One model call's token usage, normalized the same way for every platform.

    Token fields split into two groups because they answer different questions:

    * `input_tokens` / `output_tokens` are the two categories every provider reports.
      `total_tokens` is their sum: what one call cost in prompt and completion tokens.
    * `reasoning_tokens` and `cache_read_tokens` / `cache_write_tokens` are additional
      categories. On OpenCode they are additive to input and output rather than subsets
      of them, so they stay out of `total_tokens` and are reported separately through
      `consumption_tokens`. `normalization.categories` carries the evidence.

    Every token field is `None` rather than 0 when the source did not report it, so an
    unknown value is never silently read as no usage.
    """

    platform: str
    provider_id: str
    model_id: str
    session_id: str
    message_id: str
    source_event_id: str
    timestamp: datetime
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    consumption_tokens: int | None = None
    usage_status: UsageStatus = "reported"
    cache_overlap: str = "additive"
    reasoning_overlap: str = "additive"
    raw_usage: dict[str, Any] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    """What a collector found when looking for its platform's local data."""

    platform: str
    available: bool
    source_path: str
    storage_format: str
    detail: str = ""
