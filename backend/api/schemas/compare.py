"""Pydantic response models for trend comparison endpoint."""

from __future__ import annotations

from pydantic import BaseModel

from backend.api.schemas.trends import TimelinePoint


class CompareTimelineItem(BaseModel):
    group_id: str
    title: str
    points: list[TimelinePoint]


class CompareTimelineResponse(BaseModel):
    interval: str
    trends: list[CompareTimelineItem]
