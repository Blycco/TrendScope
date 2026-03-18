"""GET /api/v1/trends/{keyword}/insights — Pro+ plan-gated action insights."""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Query, Request

from backend.api.middleware.quota import check_insight_quota
from backend.api.middleware.rate_limit import rate_limit_check
from backend.api.schemas.insights import (
    CreatorInsight,
    GeneralInsight,
    InsightRequest,
    InsightResponse,
    MarketerInsight,
    OwnerInsight,
)
from backend.auth.dependencies import CurrentUser, require_plan
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.insights import (
    fetch_news_for_keyword,
    fetch_sns_for_keyword,
    increment_insight_usage,
)
from backend.processor.algorithms.action_insight import ActionInsightEngine, SourceItem
from backend.processor.shared.ai_config import get_ai_config

router = APIRouter(tags=["insights"])
logger = structlog.get_logger(__name__)


def _parse_content(
    role: str,
    content_dict: dict,
) -> MarketerInsight | CreatorInsight | OwnerInsight | GeneralInsight:
    if role == "marketer":
        return MarketerInsight(
            **{k: content_dict.get(k, []) for k in ["ad_opportunities", "source_urls"]}
        )
    elif role == "creator":
        return CreatorInsight(
            title_drafts=content_dict.get("title_drafts", []),
            timing=content_dict.get("timing", ""),
            seo_keywords=content_dict.get("seo_keywords", []),
            source_urls=content_dict.get("source_urls", []),
        )
    elif role == "owner":
        return OwnerInsight(
            **{
                k: content_dict.get(k, [])
                for k in ["consumer_reactions", "product_hints", "market_ops", "source_urls"]
            }
        )
    else:  # general
        keys = ["sns_drafts", "engagement_methods", "source_urls"]
        return GeneralInsight(**{k: content_dict.get(k, []) for k in keys})


@router.get("/trends/{keyword}/insights", response_model=InsightResponse)
async def get_trend_insights(
    keyword: str,
    request: Request,
    role: str = Query(default="general"),
    locale: str = Query(default="ko"),
    current_user: CurrentUser = Depends(require_plan("pro", status_code=402)),  # noqa: B008
    _rate_limit: CurrentUser = Depends(rate_limit_check),  # noqa: B008
    _quota: CurrentUser = Depends(check_insight_quota),  # noqa: B008
) -> InsightResponse:
    """Return AI-generated action insights for a keyword, gated to Pro+ users."""
    try:
        decoded_keyword = urllib.parse.unquote(keyword)

        role = role if role in {"marketer", "creator", "owner", "general"} else current_user.role

        pool = request.app.state.db_pool

        ai_config = await get_ai_config(pool)

        news_rows = await fetch_news_for_keyword(pool, decoded_keyword, limit=10)
        sns_rows = await fetch_sns_for_keyword(pool, decoded_keyword, limit=20)

        sources: list[SourceItem] = []
        for row in news_rows:
            sources.append(
                SourceItem(
                    title=row["title"],
                    body=row.get("body") or row["title"],
                    url=row["url"],
                    source_type="news",
                )
            )
        for row in sns_rows:
            sources.append(
                SourceItem(
                    title=row["keyword"],
                    body=row["keyword"],
                    url=f"https://trends.trendscope.app/sns/{row['platform']}/{row['keyword']}",
                    source_type="sns",
                )
            )

        engine = ActionInsightEngine(pool, ai_config)
        insight_req = InsightRequest(keyword=decoded_keyword, role=role, locale=locale)
        result = await engine.generate(insight_req, sources)

        today_reset_at = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        async with pool.acquire() as conn:
            await write_audit_log(
                conn=conn,
                user_id=current_user.user_id,
                action="insight_generated",
                target_type="keyword",
                target_id=decoded_keyword,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                detail={"role": role, "locale": locale, "cached": result["cached"]},
            )

        await increment_insight_usage(pool, current_user.user_id, "insights", today_reset_at)

        content_obj = _parse_content(role, result["content"])

        return InsightResponse(
            keyword=decoded_keyword,
            role=role,
            locale=locale,
            content=content_obj,
            cached=result["cached"],
            degraded=result["degraded"],
            generated_at=datetime.now(timezone.utc),
        )

    except Exception as exc:
        logger.error(
            "insight_generation_failed",
            keyword=keyword,
            role=role,
            user_id=getattr(current_user, "user_id", None),
            error=str(exc),
        )
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Insight generation failed",
            status_code=500,
        )
