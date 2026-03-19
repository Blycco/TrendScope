"""Pydantic schemas for personalization API."""

from __future__ import annotations

from pydantic import BaseModel


class PersonalizationResponse(BaseModel):
    category_weights: dict[str, float]
    locale_ratio: float


class PersonalizationUpdate(BaseModel):
    category_weights: dict[str, float] = {}
    locale_ratio: float = 0.5
