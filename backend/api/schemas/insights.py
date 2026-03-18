"""Pydantic schemas for action insight responses. (RULE 07: type hints)"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Role-specific content schemas
# ---------------------------------------------------------------------------


class MarketerInsight(BaseModel):
    ad_opportunities: list[str]  # 3 ad opportunity descriptions
    source_urls: list[str]  # URLs that support these opportunities (anti-hallucination)


class CreatorInsight(BaseModel):
    title_drafts: list[str]  # suggested content titles
    timing: str  # best posting time suggestion
    seo_keywords: list[str]  # SEO keywords to target
    source_urls: list[str]


class OwnerInsight(BaseModel):
    consumer_reactions: list[str]  # consumer sentiment observations
    product_hints: list[str]  # product improvement hints
    market_ops: list[str]  # market opportunity observations
    source_urls: list[str]


class GeneralInsight(BaseModel):
    sns_drafts: list[str]  # SNS post drafts
    engagement_methods: list[str]  # engagement tips
    source_urls: list[str]


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------


class InsightRequest(BaseModel):
    keyword: str
    role: str  # marketer | creator | owner | general
    locale: str = "ko"


class InsightResponse(BaseModel):
    keyword: str
    role: str
    locale: str
    content: MarketerInsight | CreatorInsight | OwnerInsight | GeneralInsight
    cached: bool
    degraded: bool  # True if TextRank fallback was used
    generated_at: datetime
