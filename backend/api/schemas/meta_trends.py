"""Pydantic schemas for meta trends and keyword history endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class MetaTrendItem(BaseModel):
    meta_title: str
    keywords: list[str]
    sub_trend_ids: list[str]
    total_score: float


class MetaTrendListResponse(BaseModel):
    items: list[MetaTrendItem]
    locale: str | None
    total: int


class KeywordFrequencyPoint(BaseModel):
    term: str
    frequency: int


class KeywordSnapshot(BaseModel):
    snapshot_at: str
    top_keywords: list[KeywordFrequencyPoint]


class KeywordHistoryResponse(BaseModel):
    group_id: str
    snapshots: list[KeywordSnapshot]
