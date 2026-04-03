"""Pydantic response models for dashboard endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_trends: int
    total_news: int
    avg_score: float
    top_category: str | None
    early_signal_count: int
    category_counts: dict[str, int]
    source_counts: dict[str, int]
