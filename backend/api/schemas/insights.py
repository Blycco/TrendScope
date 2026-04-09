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
    timing_recommendation: str = ""  # best timing to launch campaign
    channel_opportunities: list[str] = []  # recommended channels (e.g. YouTube, Instagram)
    competitor_note: str = ""  # brief competitor landscape note
    action_items: list[str] = []  # 3 concrete next steps


class CreatorInsight(BaseModel):
    title_drafts: list[str]  # suggested content titles
    timing: str  # best posting time suggestion
    seo_keywords: list[str]  # SEO keywords to target
    source_urls: list[str]
    recommended_format: str = ""  # e.g. "Short-form video", "Blog post"
    title_suggestions: list[str] = []  # alternative title ideas
    hashtag_suggestions: list[str] = []  # recommended hashtags
    best_upload_time: str = ""  # specific time + day recommendation
    action_items: list[str] = []  # 3 concrete next steps


class OwnerInsight(BaseModel):
    consumer_reactions: list[str]  # consumer sentiment observations
    product_hints: list[str]  # product improvement hints
    market_ops: list[str]  # market opportunity observations
    source_urls: list[str]
    market_opportunity: str = ""  # concise market opportunity summary
    consumer_sentiment: str = ""  # overall consumer sentiment
    product_hint: str = ""  # top product/service suggestion
    action_items: list[str] = []  # 3 concrete next steps


class GeneralInsight(BaseModel):
    sns_drafts: list[str]  # SNS post drafts
    engagement_methods: list[str]  # engagement tips
    source_urls: list[str]
    sns_post_draft: str = ""  # single polished SNS post ready to publish


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
