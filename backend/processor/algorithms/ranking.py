"""LambdaMART Learning-to-Rank with LightGBM (17 features).

Falls back to rule-based ``score_calculator.calculate_score()`` when the
trained model is unavailable or prediction fails.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import structlog

from backend.processor.shared.score_calculator import (
    _SOURCE_WEIGHTS,
    ScoreInput,
    calculate_score,
    compute_freshness,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Feature names (order matters — must match training)
# ---------------------------------------------------------------------------

FEATURE_NAMES: list[str] = [
    # Temporal (3)
    "freshness_exp",
    "hour_of_day",
    "age_bucket",
    # Source (2)
    "source_reliability",
    "diversity_bonus",
    # Engagement (4)
    "group_count",
    "social_signal",
    "ctr",
    "dwell_time",
    # Content (3)
    "body_length",
    "has_summary",
    "keyword_importance",
    # Personalization (3)
    "category_weight",
    "source_affinity",
    "cf_score",
    # Context (2)
    "fatigue_penalty",
    "diversity_bonus_mmr",
]

_NUM_FEATURES = len(FEATURE_NAMES)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LTRFeatures:
    """Extracted feature vector for a single trend group."""

    values: dict[str, float] = field(default_factory=dict)

    def to_array(self) -> list[float]:
        """Return feature vector in canonical order."""
        return [self.values.get(name, 0.0) for name in FEATURE_NAMES]


@dataclass
class EngagementStats:
    """Pre-aggregated engagement metrics for a group."""

    ctr: float = 0.0
    avg_dwell_ms: float = 0.0
    impression_count: int = 0


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def _age_bucket(minutes: float) -> int:
    """Discretise age into buckets: 0=<1h, 1=1-6h, 2=6-24h, 3=1-7d, 4=>7d."""
    if minutes < 60:
        return 0
    if minutes < 360:
        return 1
    if minutes < 1440:
        return 2
    if minutes < 10080:
        return 3
    return 4


def _source_diversity(sources: list[str]) -> float:
    """Unique source ratio as diversity signal."""
    if not sources:
        return 0.0
    return len(set(sources)) / len(sources)


def extract_features(
    *,
    published_at: datetime,
    category: str = "default",
    source_type: str = "default",
    article_count: int = 1,
    sources: list[str] | None = None,
    social_signal: float = 0.0,
    keyword_importance: float = 0.0,
    body_length: int = 0,
    has_summary: bool = False,
    engagement: EngagementStats | None = None,
    category_weight: float = 1.0,
    source_affinity: float = 0.0,
    cf_score: float = 0.0,
    fatigue_penalty: float = 0.0,
    diversity_bonus_mmr: float = 0.0,
    now: datetime | None = None,
) -> LTRFeatures:
    """Extract the 17 LTR features for a trend group."""
    if now is None:
        now = datetime.now(timezone.utc)  # noqa: UP017

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)  # noqa: UP017

    delta_minutes = max(0.0, (now - published_at).total_seconds() / 60.0)
    eng = engagement or EngagementStats()

    features = LTRFeatures(
        values={
            # Temporal
            "freshness_exp": compute_freshness(published_at, category, now),
            "hour_of_day": float(published_at.hour),
            "age_bucket": float(_age_bucket(delta_minutes)),
            # Source
            "source_reliability": _SOURCE_WEIGHTS.get(source_type, 1.0),
            "diversity_bonus": _source_diversity(sources or []),
            # Engagement
            "group_count": float(article_count),
            "social_signal": max(0.0, social_signal),
            "ctr": eng.ctr,
            "dwell_time": eng.avg_dwell_ms / 1000.0 if eng.avg_dwell_ms else 0.0,
            # Content
            "body_length": float(min(body_length, 50000)),
            "has_summary": 1.0 if has_summary else 0.0,
            "keyword_importance": max(0.0, keyword_importance),
            # Personalization
            "category_weight": category_weight,
            "source_affinity": source_affinity,
            "cf_score": cf_score,
            # Context
            "fatigue_penalty": fatigue_penalty,
            "diversity_bonus_mmr": diversity_bonus_mmr,
        }
    )
    return features


# ---------------------------------------------------------------------------
# LTR Model wrapper
# ---------------------------------------------------------------------------


class LTRModel:
    """Wrapper around a trained LightGBM ranker."""

    def __init__(self) -> None:
        self._booster: Any | None = None

    @property
    def is_loaded(self) -> bool:
        return self._booster is not None

    def load(self, path: str | Path) -> None:
        """Load a pickled LightGBM booster from disk."""
        try:
            import lightgbm as lgb  # noqa: F401

            with open(path, "rb") as f:
                self._booster = pickle.load(f)  # noqa: S301
            logger.info("ltr_model_loaded", path=str(path))
        except Exception as exc:
            logger.warning("ltr_model_load_failed", path=str(path), error=str(exc))
            self._booster = None

    def save(self, path: str | Path) -> None:
        """Persist the trained booster to disk."""
        if self._booster is None:
            raise ValueError("No model to save")
        with open(path, "wb") as f:
            pickle.dump(self._booster, f)
        logger.info("ltr_model_saved", path=str(path))

    def train(
        self,
        features: list[list[float]],
        labels: list[float],
        group_sizes: list[int],
    ) -> None:
        """Train a LambdaMART ranker on pairwise training data.

        Args:
            features: 2D feature matrix (n_samples x 17).
            labels: Relevance labels (higher = more relevant).
            group_sizes: Number of items per query group.
        """
        try:
            import lightgbm as lgb

            train_data = lgb.Dataset(
                np.array(features),
                label=np.array(labels),
                group=group_sizes,
            )
            params = {
                "objective": "lambdarank",
                "metric": "ndcg",
                "ndcg_eval_at": [5, 10],
                "learning_rate": 0.05,
                "num_leaves": 31,
                "min_data_in_leaf": 10,
                "verbose": -1,
            }
            self._booster = lgb.train(params, train_data, num_boost_round=100)
            logger.info("ltr_model_trained", n_samples=len(labels), n_groups=len(group_sizes))
        except Exception as exc:
            logger.error("ltr_model_train_failed", error=str(exc))
            self._booster = None

    def predict(self, features: LTRFeatures) -> float | None:
        """Predict relevance score for a single item.

        Returns None if the model is not loaded or prediction fails.
        """
        if self._booster is None:
            return None
        try:
            arr = np.array([features.to_array()])
            scores = self._booster.predict(arr)
            return float(scores[0])
        except Exception as exc:
            logger.warning("ltr_predict_failed", error=str(exc))
            return None


# ---------------------------------------------------------------------------
# Score function with LTR → rule-based fallback
# ---------------------------------------------------------------------------

# Module-level singleton (loaded once, reused)
_global_model = LTRModel()


def get_global_model() -> LTRModel:
    """Access the module-level LTR model singleton."""
    return _global_model


def ltr_score_or_fallback(
    features: LTRFeatures,
    score_input: ScoreInput,
    model: LTRModel | None = None,
) -> float:
    """Score using LTR model; fall back to rule-based if unavailable.

    Args:
        features: Extracted LTR features.
        score_input: Input for rule-based fallback.
        model: LTR model to use (defaults to global singleton).

    Returns:
        Predicted relevance score.
    """
    mdl = model or _global_model
    ltr_result = mdl.predict(features)
    if ltr_result is not None:
        return ltr_result

    result = calculate_score(score_input)
    return result.total


# ---------------------------------------------------------------------------
# Training data extraction (from user_action_log)
# ---------------------------------------------------------------------------


async def extract_training_data(
    pool: object,
    *,
    days: int = 30,
    min_impressions: int = 5,
) -> tuple[list[list[float]], list[float], list[int]]:
    """Extract pairwise training data from user_action_log.

    Groups by user session, uses click/dwell as relevance signal.
    Returns (features_matrix, labels, group_sizes).

    NOTE: This requires sufficient user data (MAU 300+).
    Returns empty lists if insufficient data.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    ual.item_id::text AS group_id,
                    COUNT(*) FILTER (WHERE ual.action = 'click') AS clicks,
                    COUNT(*) FILTER (WHERE ual.action IN ('click', 'page_view')) AS impressions,
                    AVG(ual.dwell_ms) FILTER (WHERE ual.dwell_ms > 0) AS avg_dwell,
                    ng.category,
                    ng.score AS current_score,
                    ng.created_at AS published_at,
                    COALESCE(array_length(ng.keywords, 1), 0) AS keyword_count
                FROM user_action_log ual
                JOIN news_group ng ON ng.id = ual.item_id
                WHERE ual.item_type = 'trend'
                  AND ual.created_at > NOW() - make_interval(days => $1)
                GROUP BY ual.item_id, ng.category, ng.score, ng.created_at, ng.keywords
                HAVING COUNT(*) FILTER (WHERE ual.action IN ('click', 'page_view')) >= $2
                ORDER BY impressions DESC
                """,
                days,
                min_impressions,
            )

        if len(rows) < 10:
            logger.info("ltr_insufficient_training_data", row_count=len(rows))
            return [], [], []

        features_list: list[list[float]] = []
        labels: list[float] = []

        for row in rows:
            ctr = row["clicks"] / max(row["impressions"], 1)
            avg_dwell = row["avg_dwell"] or 0.0
            relevance = 2.0 * ctr + 0.5 * min(avg_dwell / 30000.0, 1.0)

            feat = extract_features(
                published_at=row["published_at"] or datetime.now(timezone.utc),  # noqa: UP017
                category=row["category"] or "default",
                article_count=row["keyword_count"],
                social_signal=0.0,
                keyword_importance=0.0,
                engagement=EngagementStats(
                    ctr=ctr,
                    avg_dwell_ms=avg_dwell,
                    impression_count=row["impressions"],
                ),
            )
            features_list.append(feat.to_array())
            labels.append(relevance)

        # Single group for now (global ranking)
        group_sizes = [len(labels)]

        logger.info("ltr_training_data_extracted", n_samples=len(labels))
        return features_list, labels, group_sizes

    except Exception as exc:
        logger.error("ltr_extract_training_data_failed", error=str(exc))
        return [], [], []
