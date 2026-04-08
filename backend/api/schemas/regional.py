"""Pydantic response models for regional trend distribution endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class TrendItemMinimal(BaseModel):
    id: str
    title: str
    score: float


class RegionalTrendEntry(BaseModel):
    locale: str
    count: int
    top_trends: list[TrendItemMinimal]


class RegionalTrendResponse(BaseModel):
    entries: list[RegionalTrendEntry]
    total_locales: int
