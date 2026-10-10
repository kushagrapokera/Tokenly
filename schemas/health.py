"""Response shapes for the health endpoint."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Application health summary returned by the health endpoint."""

    status: Literal["ok"]
    app: str
    version: str
    database_connected: bool
