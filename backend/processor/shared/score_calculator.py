"""Freshness decay scoring for trend items.

Normalized scoring (0-100) with weighted components:
  - freshness:          40 points (time decay)
  - source_diversity:   15 points (unique source count)
  - article_count:      20 points (articles in group)
  - social_signal:      15 points (social engagement)
  - keyword_importance: 10 points (keyword relevance)

Raw total preserved for debugging.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)

# ── Weight allocation (must sum to 100) ──────────────────────────────────
WEIGHT_FRESHNESS: float = 40.0
WEIGHT_SOURCE_DIVERSITY: float = 15.0
WEIGHT_ARTICLE_COUNT: float = 20.0
WEIGHT_SOCIAL_SIGNAL: float = 15.0
WEIGHT_KEYWORD_IMPORTANCE: float = 10.0


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

# Source reliability weights (kept for raw total backward compat)
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
    source_count: int = 1
    social_signal: float = 0.0
    keyword_importance: float = 0.0


@dataclass
class ScoreResult:
    """Calculated score with component breakdown."""

    total: float
    normalized: float
    freshness: float
    source_weight: float
    article_count_bonus: float
    social_signal: float
    keyword_importance: float
    source_diversity: float


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


def _normalize_freshness(raw_freshness: float) -> float:
    """Map freshness (0-100) to weighted points (0-WEIGHT_FRESHNESS)."""
    return (min(raw_freshness, 100.0) / 100.0) * WEIGHT_FRESHNESS


def _normalize_source_diversity(source_count: int) -> float:
    """Map unique source count to weighted points (0-WEIGHT_SOURCE_DIVERSITY).

    Uses log curve: 5+ unique sources => full score.
    """
    if source_count <= 0:
        return 0.0
    ratio = min(1.0, math.log2(source_count + 1) / math.log2(6))
    return ratio * WEIGHT_SOURCE_DIVERSITY


def _normalize_article_count(article_count: int) -> float:
    """Map article count to weighted points (0-WEIGHT_ARTICLE_COUNT).

    Uses log curve: 10+ articles => full score.
    """
    if article_count <= 0:
        return 0.0
    ratio = min(1.0, math.log2(article_count + 1) / math.log2(11))
    return ratio * WEIGHT_ARTICLE_COUNT


def _normalize_social_signal(social_signal: float) -> float:
    """Map social engagement to weighted points (0-WEIGHT_SOCIAL_SIGNAL).

    Uses log curve: signal >= 50 => full score.
    """
    if social_signal <= 0:
        return 0.0
    ratio = min(1.0, math.log2(social_signal + 1) / math.log2(51))
    return ratio * WEIGHT_SOCIAL_SIGNAL


def _normalize_keyword_importance(keyword_importance: float) -> float:
    """Map keyword relevance (0-1 typical) to weighted points (0-WEIGHT_KEYWORD_IMPORTANCE)."""
    clamped = max(0.0, min(keyword_importance, 1.0))
    return clamped * WEIGHT_KEYWORD_IMPORTANCE


def calculate_score(score_input: ScoreInput, now: datetime | None = None) -> ScoreResult:
    """Calculate the composite trend score with normalized 0-100 output.

    Normalized = sum of weighted components (freshness 40, source_diversity 15,
    article_count 20, social_signal 15, keyword_importance 10).
    Raw total preserved for backward compatibility and debugging.

    Args:
        score_input: Input parameters.
        now: Current time override for testing.

    Returns:
        ScoreResult with total (raw), normalized (0-100), and component breakdown.
    """
    freshness = compute_freshness(score_input.published_at, score_input.category, now)
    source_weight = _get_source_weight(score_input.source_type)
    article_bonus = _compute_article_count_bonus(score_input.article_count)
    social = max(0.0, score_input.social_signal)
    keyword_imp = max(0.0, score_input.keyword_importance)

    # Raw total (backward compatible)
    total = freshness + source_weight + article_bonus + social + keyword_imp

    # Normalized 0-100 weighted score
    n_freshness = _normalize_freshness(freshness)
    n_source_div = _normalize_source_diversity(score_input.source_count)
    n_article = _normalize_article_count(score_input.article_count)
    n_social = _normalize_social_signal(social)
    n_keyword = _normalize_keyword_importance(keyword_imp)

    normalized = round(n_freshness + n_source_div + n_article + n_social + n_keyword, 2)

    return ScoreResult(
        total=total,
        normalized=normalized,
        freshness=freshness,
        source_weight=source_weight,
        article_count_bonus=article_bonus,
        social_signal=social,
        keyword_importance=keyword_imp,
        source_diversity=n_source_div,
    )
