"""Regional trend distribution endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from backend.api.schemas.regional import RegionalTrendEntry, RegionalTrendResponse, TrendItemMinimal
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["regional"])

_CACHE_TTL = 1800  # 30 minutes


@router.get("/trends/regional", response_model=RegionalTrendResponse)
async def get_regional_trends(request: Request) -> Response:
    """Return locale-based trend distribution for the past 24 hours. Cache: 30m."""
    cache_key = "trends_regional"

    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/json")
    except Exception as exc:
        logger.warning("regional_cache_get_failed", error=str(exc))

    try:
        db_pool = request.app.state.db_pool
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT locale, COUNT(*)::int AS count
                FROM news_group
                WHERE created_at > now() - interval '24 hours'
                  AND locale IS NOT NULL
                GROUP BY locale
                ORDER BY count DESC
                LIMIT 20
                """
            )

        entries: list[RegionalTrendEntry] = []
        for row in rows:
            locale = row["locale"]
            async with db_pool.acquire() as conn:
                top_rows = await conn.fetch(
                    "SELECT id::text, title, score FROM news_group "
                    "WHERE locale = $1 AND created_at > now() - interval '24 hours' "
                    "ORDER BY score DESC LIMIT 3",
                    locale,
                )
            entries.append(
                RegionalTrendEntry(
                    locale=locale,
                    count=row["count"],
                    top_trends=[
                        TrendItemMinimal(id=r["id"], title=r["title"], score=r["score"])
                        for r in top_rows
                    ],
                )
            )

        response_data = RegionalTrendResponse(
            entries=entries,
            total_locales=len(entries),
        )
        content = response_data.model_dump_json().encode()

        try:
            await set_cached(cache_key, content, _CACHE_TTL)
        except Exception as exc:
            logger.warning("regional_cache_set_failed", error=str(exc))

        return Response(content=content, media_type="application/json")

    except Exception as exc:
        logger.warning("get_regional_trends_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Internal error") from exc
