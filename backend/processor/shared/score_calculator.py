"""Freshness decay scoring for trend items.

Normalized scoring (0-100) with weighted components:
  - freshness:          25 points (time decay)
  - burst:             25 points (burst detection score)
  - article_count:     15 points (articles in group)
  - source_diversity:  12 points (unique source count)
  - social_signal:     10 points (social engagement)
  - keyword_importance: 8 points (keyword relevance)
  - velocity:           5 points (growth velocity)

Raw total preserved for debugging.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)

# ── Default weight allocation (must sum to 100) ───────────────────────────
WEIGHT_FRESHNESS: float = 25.0
WEIGHT_BURST: float = 25.0
WEIGHT_ARTICLE_COUNT: float = 15.0
WEIGHT_SOURCE_DIVERSITY: float = 12.0
WEIGHT_SOCIAL_SIGNAL: float = 10.0
WEIGHT_KEYWORD_IMPORTANCE: float = 8.0
WEIGHT_VELOCITY: float = 5.0

# Single-article cluster penalty
_SINGLE_ARTICLE_PENALTY: float = 0.7


@dataclass
class ScoreWeights:
    """Score weight configuration — loaded from DB admin_settings."""

    freshness: float = WEIGHT_FRESHNESS
    burst: float = WEIGHT_BURST
    article_count: float = WEIGHT_ARTICLE_COUNT
    source_diversity: float = WEIGHT_SOURCE_DIVERSITY
    social_signal: float = WEIGHT_SOCIAL_SIGNAL
    keyword_importance: float = WEIGHT_KEYWORD_IMPORTANCE
    velocity: float = WEIGHT_VELOCITY


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
    burst_score: float = 0.0
    velocity: float = 0.0


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
    burst: float = 0.0


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


def _normalize_freshness(raw_freshness: float, weight: float) -> float:
    """Map freshness (0-100) to weighted points."""
    return (min(raw_freshness, 100.0) / 100.0) * weight


def _normalize_source_diversity(source_count: int, weight: float) -> float:
    """Map unique source count to weighted points. Log curve: 5+ sources => full."""
    if source_count <= 0:
        return 0.0
    ratio = min(1.0, math.log2(source_count + 1) / math.log2(6))
    return ratio * weight


def _normalize_article_count(article_count: int, weight: float) -> float:
    """Map article count to weighted points. Log curve: 10+ articles => full."""
    if article_count <= 0:
        return 0.0
    ratio = min(1.0, math.log2(article_count + 1) / math.log2(11))
    return ratio * weight


def _normalize_social_signal(social_signal: float, weight: float) -> float:
    """Map social engagement to weighted points. Log curve: signal>=50 => full."""
    if social_signal <= 0:
        return 0.0
    ratio = min(1.0, math.log2(social_signal + 1) / math.log2(51))
    return ratio * weight


def _normalize_keyword_importance(keyword_importance: float, weight: float) -> float:
    """Map keyword relevance (0-1) to weighted points."""
    clamped = max(0.0, min(keyword_importance, 1.0))
    return clamped * weight


def _normalize_burst(burst_score: float, weight: float) -> float:
    """Map burst score (0-1) to weighted points."""
    clamped = max(0.0, min(burst_score, 1.0))
    return clamped * weight


def _normalize_velocity(velocity: float, weight: float) -> float:
    """Map velocity (0-1) to weighted points."""
    clamped = max(0.0, min(velocity, 1.0))
    return clamped * weight


def calculate_score(
    score_input: ScoreInput,
    weights: ScoreWeights | None = None,
    now: datetime | None = None,
) -> ScoreResult:
    """Calculate the composite trend score with normalized 0-100 output.

    Args:
        score_input: Input parameters including burst_score and velocity.
        weights: Weight configuration loaded from DB. Uses defaults if None.
        now: Current time override for testing.

    Returns:
        ScoreResult with total (raw), normalized (0-100), and component breakdown.
    """
    w = weights or ScoreWeights()

    freshness = compute_freshness(score_input.published_at, score_input.category, now)
    source_weight = _get_source_weight(score_input.source_type)
    article_bonus = _compute_article_count_bonus(score_input.article_count)
    social = max(0.0, score_input.social_signal)
    keyword_imp = max(0.0, score_input.keyword_importance)

    # Raw total (backward compatible)
    total = freshness + source_weight + article_bonus + social + keyword_imp

    # Normalized 0-100 weighted score
    n_freshness = _normalize_freshness(freshness, w.freshness)
    n_source_div = _normalize_source_diversity(score_input.source_count, w.source_diversity)
    n_article = _normalize_article_count(score_input.article_count, w.article_count)
    n_social = _normalize_social_signal(social, w.social_signal)
    n_keyword = _normalize_keyword_importance(keyword_imp, w.keyword_importance)
    n_burst = _normalize_burst(score_input.burst_score, w.burst)
    n_velocity = _normalize_velocity(score_input.velocity, w.velocity)

    normalized = round(
        n_freshness + n_source_div + n_article + n_social + n_keyword + n_burst + n_velocity,
        2,
    )

    # Single-article cluster penalty
    if score_input.article_count == 1:
        normalized = round(normalized * _SINGLE_ARTICLE_PENALTY, 2)

    return ScoreResult(
        total=total,
        normalized=normalized,
        freshness=freshness,
        source_weight=source_weight,
        article_count_bonus=article_bonus,
        social_signal=social,
        keyword_importance=keyword_imp,
        source_diversity=n_source_div,
        burst=n_burst,
    )
