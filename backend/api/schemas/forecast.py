"""Pydantic response models for trend forecast endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class ForecastPoint(BaseModel):
    date: str
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ForecastResponse(BaseModel):
    group_id: str
    horizon_days: int
    points: list[ForecastPoint]
