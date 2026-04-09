"""GET /api/v1/trends/{group_id}/insights — Pro+ plan-gated action insights."""

from __future__ import annotations

import re
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
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.insights import (
    fetch_group_info,
    fetch_news_for_keyword,
    fetch_news_for_keywords,
    fetch_sns_for_keyword,
    fetch_sns_for_keywords,
    increment_insight_usage,
)
from backend.processor.algorithms.action_insight import ActionInsightEngine, SourceItem
from backend.processor.shared.ai_config import get_ai_config

router = APIRouter(tags=["insights"])
logger = structlog.get_logger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _parse_content(
    role: str,
    content_dict: dict,
) -> MarketerInsight | CreatorInsight | OwnerInsight | GeneralInsight:
    if role == "marketer":
        return MarketerInsight(
            ad_opportunities=content_dict.get("ad_opportunities", []),
            source_urls=content_dict.get("source_urls", []),
            timing_recommendation=content_dict.get("timing_recommendation", ""),
            channel_opportunities=content_dict.get("channel_opportunities", []),
            competitor_note=content_dict.get("competitor_note", ""),
            action_items=content_dict.get("action_items", []),
        )
    elif role == "creator":
        return CreatorInsight(
            title_drafts=content_dict.get("title_drafts", []),
            timing=content_dict.get("timing", ""),
            seo_keywords=content_dict.get("seo_keywords", []),
            source_urls=content_dict.get("source_urls", []),
            recommended_format=content_dict.get("recommended_format", ""),
            title_suggestions=content_dict.get("title_suggestions", []),
            hashtag_suggestions=content_dict.get("hashtag_suggestions", []),
            best_upload_time=content_dict.get("best_upload_time", ""),
            action_items=content_dict.get("action_items", []),
        )
    elif role == "owner":
        return OwnerInsight(
            consumer_reactions=content_dict.get("consumer_reactions", []),
            product_hints=content_dict.get("product_hints", []),
            market_ops=content_dict.get("market_ops", []),
            source_urls=content_dict.get("source_urls", []),
            market_opportunity=content_dict.get("market_opportunity", ""),
            consumer_sentiment=content_dict.get("consumer_sentiment", ""),
            product_hint=content_dict.get("product_hint", ""),
            action_items=content_dict.get("action_items", []),
        )
    else:  # general
        return GeneralInsight(
            sns_drafts=content_dict.get("sns_drafts", []),
            engagement_methods=content_dict.get("engagement_methods", []),
            source_urls=content_dict.get("source_urls", []),
            sns_post_draft=content_dict.get("sns_post_draft", ""),
        )


@router.get("/trends/{group_id}/insights", response_model=InsightResponse)
@handle_errors(
    error_code=ErrorCode.INTERNAL_ERROR,
    message="Insight generation failed",
    status_code=500,
    log_event="insight_generation_failed",
)
async def get_trend_insights(
    group_id: str,
    request: Request,
    role: str = Query(default="general"),
    locale: str = Query(default="ko"),
    current_user: CurrentUser = Depends(require_plan("pro", status_code=402)),  # noqa: B008
    _rate_limit: CurrentUser = Depends(rate_limit_check),  # noqa: B008
    _quota: CurrentUser = Depends(check_insight_quota),  # noqa: B008
) -> InsightResponse:
    """Return AI-generated action insights for a trend group or keyword.

    Accepts either a UUID (news_group.id) or a keyword string.
    When a UUID is given, resolves the group's title and keywords for source lookup.
    """
    decoded_input = urllib.parse.unquote(group_id)

    role = role if role in {"marketer", "creator", "owner", "general"} else current_user.role

    pool = request.app.state.db_pool

    ai_config = await get_ai_config(pool)

    # Resolve keywords: UUID → look up group title/keywords, else use as keyword
    if _UUID_RE.match(decoded_input):
        group_info = await fetch_group_info(pool, decoded_input)
        if not group_info:
            return error_response(ErrorCode.NOT_FOUND, "Trend group not found", status_code=404)
        resolved_keyword = group_info["title"]
        search_keywords = list(group_info["keywords"] or [])
        if resolved_keyword and resolved_keyword not in search_keywords:
            search_keywords.insert(0, resolved_keyword)
        # Use multi-keyword search for better results
        news_rows = await fetch_news_for_keywords(pool, search_keywords, limit=10)
        sns_rows = await fetch_sns_for_keywords(pool, search_keywords, limit=20)
    else:
        resolved_keyword = decoded_input
        news_rows = await fetch_news_for_keyword(pool, decoded_input, limit=10)
        sns_rows = await fetch_sns_for_keyword(pool, decoded_input, limit=20)

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
    insight_req = InsightRequest(keyword=resolved_keyword, role=role, locale=locale)
    result = await engine.generate(insight_req, sources)

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="insight_generated",
        target_type="keyword",
        target_id=resolved_keyword,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"role": role, "locale": locale, "cached": result["cached"]},
    )

    today_reset_at = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    await increment_insight_usage(pool, current_user.user_id, "insights", today_reset_at)

    content_obj = _parse_content(role, result["content"])

    return InsightResponse(
        keyword=resolved_keyword,
        role=role,
        locale=locale,
        content=content_obj,
        cached=result["cached"],
        degraded=result["degraded"],
        generated_at=datetime.now(timezone.utc),
    )
