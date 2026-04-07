"""GET /api/v1/forecast/{group_id} — 12-month trend forecast (Pro+ plan gate)."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from backend.api.schemas.forecast import ForecastPoint, ForecastResponse
from backend.auth.dependencies import CurrentUser, require_plan
from backend.common.errors import ErrorCode, error_response
from backend.processor.algorithms.prediction import forecast_trend
from backend.processor.shared.cache_manager import get_cached, set_cached

router = APIRouter(tags=["forecast"])
logger = structlog.get_logger(__name__)

_FORECAST_CACHE_TTL = 3600  # 1 hour


def _cache_key(group_id: str, horizon: int) -> str:
    return f"forecast:{group_id}:{horizon}"


@router.get("/forecast/{group_id}", response_model=ForecastResponse)
async def get_forecast(
    group_id: str,
    request: Request,
    horizon: int = Query(default=365, ge=30, le=730),
    current_user: CurrentUser = Depends(require_plan("pro")),  # noqa: B008
) -> Response:
    """Return trend forecast for the given group.

    Plan gate: Pro+ only (RULE 08 — server-side enforcement).
    Results are cached in Redis with 1-hour TTL (RULE 18).
    """
    cache_key = _cache_key(group_id, horizon)

    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/json")
    except Exception as exc:
        logger.warning("forecast_cache_read_failed", error=str(exc))

    try:
        pool = request.app.state.db_pool
        points_raw = await forecast_trend(
            group_id=group_id,
            db_pool=pool,
            horizon_days=horizon,
        )
    except Exception as exc:
        logger.error(
            "forecast_generation_failed",
            group_id=group_id,
            error=str(exc),
        )
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Forecast generation failed",
            status_code=500,
        )

    if not points_raw:
        return error_response(
            ErrorCode.NOT_FOUND,
            "Insufficient data for forecast",
            status_code=404,
        )

    points = [
        ForecastPoint(
            date=p["date"],
            yhat=p["yhat"],
            yhat_lower=p["yhat_lower"],
            yhat_upper=p["yhat_upper"],
        )
        for p in points_raw
    ]

    body = ForecastResponse(
        group_id=group_id,
        horizon_days=horizon,
        points=points,
    )
    body_bytes = body.model_dump_json().encode()

    try:
        await set_cached(cache_key, body_bytes, _FORECAST_CACHE_TTL)
    except Exception as exc:
        logger.warning("forecast_cache_write_failed", error=str(exc))

    return Response(content=body_bytes, media_type="application/json")
