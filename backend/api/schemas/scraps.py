"""Pydantic models for scrap endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ScrapCreate(BaseModel):
    item_type: str
    item_id: str
    user_tags: list[str] | None = None
    memo: str | None = None


class ScrapResponse(BaseModel):
    id: str
    user_id: str
    item_type: str
    item_id: str
    user_tags: list[str]
    memo: str | None
    created_at: datetime


class ScrapListResponse(BaseModel):
    items: list[ScrapResponse]
    total: int
