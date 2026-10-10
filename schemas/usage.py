"""Normalized usage record shared by every collector, refined as normalization lands."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

UsageStatus = Literal["reported", "estimated", "unavailable"]


class UsageRecord(BaseModel):
    """One model call's token usage, normalized the same way for every platform."""

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
    usage_status: UsageStatus = "reported"
    raw_usage: dict[str, Any] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    """What a collector found when looking for its platform's local data."""

    platform: str
    available: bool
    source_path: str
    storage_format: str
    detail: str = ""
