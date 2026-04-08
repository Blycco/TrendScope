"""GET /api/v1/dashboard/summary endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import Response

from backend.api.schemas.dashboard import DashboardSummaryResponse
from backend.common.decorators import handle_errors
from backend.db.queries.dashboard import fetch_dashboard_summary
from backend.processor.shared.cache_manager import get_cached, set_cached

router = APIRouter(tags=["dashboard"])
logger = structlog.get_logger(__name__)

_CACHE_KEY = "dashboard:summary"
_CACHE_TTL = 180  # 3 minutes


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
@handle_errors(log_event="dashboard_summary_failed")
async def get_dashboard_summary(request: Request) -> Response:
    """Return aggregated dashboard stats for the last 24 hours."""
    cached = await get_cached(_CACHE_KEY)
    if cached is not None:
        return Response(content=cached, media_type="application/json")

    pool = request.app.state.db_pool
    data = await fetch_dashboard_summary(pool)

    resp = DashboardSummaryResponse(**data)
    body = resp.model_dump_json().encode()
    await set_cached(_CACHE_KEY, body, _CACHE_TTL)
    return Response(content=body, media_type="application/json")
