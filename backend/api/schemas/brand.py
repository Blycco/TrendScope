"""Pydantic schemas for Brand Monitoring API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BrandCreateRequest(BaseModel):
    brand_name: str = Field(..., min_length=1, max_length=100)
    keywords: list[str] = Field(default_factory=list)
    slack_webhook: str | None = None


class BrandMonitorRequest(BaseModel):
    texts: list[str] = Field(default_factory=list)


class BrandMentionItem(BaseModel):
    text: str
    label: str
    score: float


class BrandMonitorResponse(BaseModel):
    brand_name: str
    current_score: float
    mean_24h: float
    std_24h: float
    z_score: float
    alert_threshold: float
    is_crisis: bool
    label: str
    cached: bool
    mentions: list[BrandMentionItem]


class BrandItem(BaseModel):
    id: str
    brand_name: str
    keywords: list[str]
    is_active: bool
    slack_webhook: str | None
    last_alerted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BrandListResponse(BaseModel):
    brands: list[BrandItem]


class BrandCreateResponse(BaseModel):
    id: str
    brand_name: str
    keywords: list[str]
    slack_webhook: str | None
    created_at: datetime
