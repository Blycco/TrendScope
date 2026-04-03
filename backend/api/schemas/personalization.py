"""Pydantic schemas for personalization API."""

from __future__ import annotations

from pydantic import BaseModel


class PersonalizationResponse(BaseModel):
    category_weights: dict[str, float]
    locale_ratio: float


class PersonalizationUpdate(BaseModel):
    category_weights: dict[str, float] = {}
    locale_ratio: float = 0.5


class BehaviorStatsResponse(BaseModel):
    category_counts: dict[str, int]
    total_events: int
    action_counts: dict[str, int]
    suggested_weights: dict[str, float]
