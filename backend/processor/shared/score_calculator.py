"""Freshness decay scoring for trend items.

Formula: freshness = 100 * exp(-lambda * t_minutes)
Score = freshness + source_weight + article_count_bonus + social_signal + keyword_importance
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class Category(str, Enum):
    """News/trend categories with corresponding decay rates."""

    BREAKING = "breaking"
    POLITICS = "politics"
    IT = "it"
    ECONOMY = "economy"
    ENTERTAINMENT = "entertainment"
    SPORTS = "sports"
    SOCIETY = "society"
    DEFAULT = "default"


# Lambda decay rates per category (from algorithms.md)
_DECAY_LAMBDAS: dict[str, float] = {
    Category.BREAKING: 0.10,
    Category.POLITICS: 0.04,
    Category.IT: 0.02,
    Category.DEFAULT: 0.05,
}

# Source reliability weights
_SOURCE_WEIGHTS: dict[str, float] = {
    "major_news": 15.0,
    "news": 10.0,
    "community": 5.0,
    "sns": 3.0,
    "blog": 2.0,
    "default": 1.0,
}


@dataclass
class ScoreInput:
    """Input parameters for score calculation."""

    published_at: datetime
    category: str = "default"
    source_type: str = "default"
    article_count: int = 1
    social_signal: float = 0.0
    keyword_importance: float = 0.0


@dataclass
class ScoreResult:
    """Calculated score with component breakdown."""

    total: float
    freshness: float
    source_weight: float
    article_count_bonus: float
    social_signal: float
    keyword_importance: float


def _get_decay_lambda(category: str) -> float:
    """Get the decay lambda for a category."""
    return _DECAY_LAMBDAS.get(category, _DECAY_LAMBDAS[Category.DEFAULT])


def _get_source_weight(source_type: str) -> float:
    """Get the source reliability weight."""
    return _SOURCE_WEIGHTS.get(source_type, _SOURCE_WEIGHTS["default"])


def compute_freshness(published_at: datetime, category: str, now: datetime | None = None) -> float:
    """Compute freshness score: 100 * exp(-lambda * t_minutes).

    Args:
        published_at: Publication timestamp (must be timezone-aware).
        category: Content category for decay rate selection.
        now: Current time (defaults to UTC now).

    Returns:
        Freshness score in range [0, 100].
    """
    if now is None:
        now = datetime.now(timezone.utc)  # noqa: UP017

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)  # noqa: UP017
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)  # noqa: UP017

    delta_minutes = max(0.0, (now - published_at).total_seconds() / 60.0)
    decay_lambda = _get_decay_lambda(category)
    return 100.0 * math.exp(-decay_lambda * delta_minutes)


def _compute_article_count_bonus(article_count: int) -> float:
    """Logarithmic bonus for article count (diminishing returns)."""
    if article_count <= 1:
        return 0.0
    return min(20.0, 5.0 * math.log2(article_count))


def calculate_score(score_input: ScoreInput, now: datetime | None = None) -> ScoreResult:
    """Calculate the composite trend score.

    Score = freshness + source_weight + article_count_bonus + social_signal + keyword_importance

    Args:
        score_input: Input parameters.
        now: Current time override for testing.

    Returns:
        ScoreResult with total and component breakdown.
    """
    freshness = compute_freshness(score_input.published_at, score_input.category, now)
    source_weight = _get_source_weight(score_input.source_type)
    article_bonus = _compute_article_count_bonus(score_input.article_count)
    social = max(0.0, score_input.social_signal)
    keyword_imp = max(0.0, score_input.keyword_importance)

    total = freshness + source_weight + article_bonus + social + keyword_imp

    return ScoreResult(
        total=total,
        freshness=freshness,
        source_weight=source_weight,
        article_count_bonus=article_bonus,
        social_signal=social,
        keyword_importance=keyword_imp,
    )
