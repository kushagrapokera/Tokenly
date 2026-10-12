"""Serve the dashboard and its explicit assets without shadowing API errors."""

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
WEB_DIRECTORY = Path(__file__).resolve().parents[1] / "web"
router = APIRouter(include_in_schema=False)


def _dashboard_asset(filename: str) -> FileResponse:
    logger.debug("serving dashboard asset %s", filename)
    return FileResponse(WEB_DIRECTORY / filename, headers={"Cache-Control": "no-store"})


@router.get("/")
def serve_dashboard() -> FileResponse:
    return _dashboard_asset("index.html")


@router.get("/app.js")
def serve_dashboard_script() -> FileResponse:
    return _dashboard_asset("app.js")


@router.get("/usage-filters.js")
def serve_usage_filters() -> FileResponse:
    return _dashboard_asset("usage-filters.js")


@router.get("/usage-chart.js")
def serve_usage_chart() -> FileResponse:
    return _dashboard_asset("usage-chart.js")


@router.get("/platform-cards.js")
def serve_platform_cards() -> FileResponse:
    return _dashboard_asset("platform-cards.js")


@router.get("/usage-breakdown.js")
def serve_usage_breakdown() -> FileResponse:
    return _dashboard_asset("usage-breakdown.js")


@router.get("/usage-cards.js")
def serve_usage_cards() -> FileResponse:
    return _dashboard_asset("usage-cards.js")


@router.get("/dropdowns.js")
def serve_dropdowns() -> FileResponse:
    return _dashboard_asset("dropdowns.js")


@router.get("/model-ranking.js")
def serve_model_ranking() -> FileResponse:
    return _dashboard_asset("model-ranking.js")
