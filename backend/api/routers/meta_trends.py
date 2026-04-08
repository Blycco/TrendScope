"""Meta trends and keyword history endpoints.

D2: GET /api/v1/trends/meta          — 메타 트렌드 목록 (TTL 1h)
D3: GET /api/v1/trends/{id}/keywords/history — 연관어 변화 히스토리 (TTL 30m)
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from backend.api.schemas.meta_trends import (
    KeywordFrequencyPoint,
    KeywordHistoryResponse,
    KeywordSnapshot,
    MetaTrendItem,
    MetaTrendListResponse,
)
from backend.db.queries.keyword_history import fetch_keyword_history
from backend.db.queries.meta_trends import fetch_groups_for_meta
from backend.processor.algorithms.meta_clusterer import cluster_groups_by_keywords
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["meta_trends"])

_META_CACHE_TTL = 3600  # 1h
_HISTORY_CACHE_TTL = 1800  # 30m


@router.get("/trends/meta", response_model=MetaTrendListResponse)
async def get_meta_trends(
    request: Request,
    locale: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> Response:
    """메타 트렌드 목록.

    category 내 news_group들을 Jaccard 키워드 유사도로 2차 클러스터링하여
    메타 트렌드를 반환합니다. Cache TTL: 1h.
    """
    cache_key = f"meta_trends:{locale or 'all'}"

    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/json")
    except Exception as exc:
        logger.warning("meta_trends_cache_get_failed", error=str(exc))

    try:
        db_pool = request.app.state.db_pool
        groups = await fetch_groups_for_meta(db_pool, locale=locale)
        meta_trends = cluster_groups_by_keywords(groups)[:limit]

        response_data = MetaTrendListResponse(
            items=[
                MetaTrendItem(
                    meta_title=m.meta_title,
                    keywords=m.keywords,
                    sub_trend_ids=m.sub_trend_ids,
                    total_score=m.total_score,
                )
                for m in meta_trends
            ],
            locale=locale,
            total=len(meta_trends),
        )

        content = response_data.model_dump_json().encode()
        try:
            await set_cached(cache_key, content, ttl=_META_CACHE_TTL)
        except Exception as cache_exc:
            logger.warning("meta_trends_cache_set_failed", error=str(cache_exc))

        return Response(content=content, media_type="application/json")
    except Exception as exc:
        logger.warning("get_meta_trends_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Internal error") from exc


@router.get(
    "/trends/{group_id}/keywords/history",
    response_model=KeywordHistoryResponse,
)
async def get_keyword_history(
    group_id: str,
    request: Request,
    limit: int = Query(default=10, ge=1, le=30),
) -> Response:
    """키워드 변화 히스토리.

    특정 트렌드 그룹의 keyword_snapshot 데이터를 시간순으로 반환합니다.
    Cache TTL: 30m.
    """
    cache_key = f"kw_history:{group_id}"

    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/json")
    except Exception as exc:
        logger.warning("kw_history_cache_get_failed", group_id=group_id, error=str(exc))

    try:
        db_pool = request.app.state.db_pool
        snapshots_raw = await fetch_keyword_history(db_pool, group_id, limit_snapshots=limit)

        response_data = KeywordHistoryResponse(
            group_id=group_id,
            snapshots=[
                KeywordSnapshot(
                    snapshot_at=s["snapshot_at"],
                    top_keywords=[
                        KeywordFrequencyPoint(term=k["term"], frequency=k["frequency"])
                        for k in s["top_keywords"]
                    ],
                )
                for s in snapshots_raw
            ],
        )

        content = response_data.model_dump_json().encode()
        try:
            await set_cached(cache_key, content, ttl=_HISTORY_CACHE_TTL)
        except Exception as cache_exc:
            logger.warning("kw_history_cache_set_failed", group_id=group_id, error=str(cache_exc))

        return Response(content=content, media_type="application/json")
    except Exception as exc:
        logger.warning("get_keyword_history_failed", group_id=group_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Internal error") from exc
