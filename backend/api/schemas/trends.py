"""Pydantic response models for trend and news feed endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrendItem(BaseModel):
    id: str
    title: str
    category: str
    score: float
    early_trend_score: float
    keywords: list[str]
    created_at: datetime


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
