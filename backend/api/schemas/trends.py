"""Pydantic response models for trend and news feed endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrendItem(BaseModel):
    id: str
    title: str
    category: str
    summary: str | None = None
    score: float
    early_trend_score: float
    keywords: list[str]
    created_at: datetime
    article_count: int = 0
    direction: str = "steady"
    growth_type: str = "unknown"
    status: str = "stable"
    burst_score: float = 0.0


class TrendListResponse(BaseModel):
    items: list[TrendItem]
    next_cursor: str | None
    total: int


class TrendArticleItem(BaseModel):
    id: str
    title: str
    url: str
    source: str | None
    publish_time: datetime | None
    body_snippet: str | None


class TrendDetailResponse(BaseModel):
    id: str
    title: str
    category: str
    summary: str | None
    score: float
    early_trend_score: float
    keywords: list[str]
    created_at: datetime
    direction: str = "steady"
    growth_type: str = "unknown"
    articles: list[TrendArticleItem]


class NewsItem(BaseModel):
    id: str
    title: str
    url: str
    source: str | None
    publish_time: datetime
    summary: str | None
    article_count: int = 1


class NewsListResponse(BaseModel):
    items: list[NewsItem]
    next_cursor: str | None


class TimelinePoint(BaseModel):
    timestamp: datetime
    article_count: int
    source_count: int


class TrendTimelineResponse(BaseModel):
    group_id: str
    interval: str
    points: list[TimelinePoint]


# ---------------------------------------------------------------------------
# Aspect-Based Sentiment schemas
# ---------------------------------------------------------------------------


class AspectSentimentItem(BaseModel):
    aspect: str


class SentimentDistributionResponse(BaseModel):
    positive: int
    neutral: int
    negative: int
    total: int


class AspectSentimentResponse(BaseModel):
    group_id: str
    aspects: list[AspectSentimentItem]
