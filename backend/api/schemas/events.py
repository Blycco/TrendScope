"""Pydantic models for event tracking endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class EventItem(BaseModel):
    action: str
    item_type: str | None = None
    item_id: str | None = None
    dwell_ms: int | None = None
    meta: dict | None = None


class EventBatchRequest(BaseModel):
    events: list[EventItem]
