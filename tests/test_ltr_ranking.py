"""Tests for LambdaMART LTR ranking module."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.processor.algorithms.ranking import (
    FEATURE_NAMES,
    EngagementStats,
    LTRFeatures,
    LTRModel,
    extract_features,
    ltr_score_or_fallback,
)
from backend.processor.shared.score_calculator import ScoreInput


class TestFeatureExtraction:
    def test_returns_17_features(self) -> None:
        now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        features = extract_features(
            published_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            category="it",
            source_type="major_news",
            article_count=5,
            sources=["a", "b", "a"],
            social_signal=3.0,
            keyword_importance=2.0,
            body_length=1500,
            has_summary=True,
            engagement=EngagementStats(ctr=0.15, avg_dwell_ms=25000, impression_count=100),
            category_weight=1.5,
            source_affinity=0.3,
            cf_score=0.8,
            fatigue_penalty=0.1,
            diversity_bonus_mmr=0.7,
            now=now,
        )

        arr = features.to_array()
        assert len(arr) == 17
        assert len(FEATURE_NAMES) == 17

    def test_freshness_decreases_with_age(self) -> None:
        now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        recent = extract_features(
            published_at=datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc),
            now=now,
        )
        old = extract_features(
            published_at=datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
            now=now,
        )
        assert recent.values["freshness_exp"] > old.values["freshness_exp"]

    def test_source_reliability_uses_weights(self) -> None:
        f1 = extract_features(
            published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            source_type="major_news",
        )
        f2 = extract_features(
            published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            source_type="blog",
        )
        assert f1.values["source_reliability"] == 15.0
        assert f2.values["source_reliability"] == 2.0

    def test_diversity_bonus(self) -> None:
        f = extract_features(
            published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            sources=["a", "b", "c"],
        )
        assert f.values["diversity_bonus"] == 1.0

        f2 = extract_features(
            published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            sources=["a", "a", "a"],
        )
        assert abs(f2.values["diversity_bonus"] - 1 / 3) < 0.01

    def test_has_summary_flag(self) -> None:
        f1 = extract_features(
            published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            has_summary=True,
        )
        f2 = extract_features(
            published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            has_summary=False,
        )
        assert f1.values["has_summary"] == 1.0
        assert f2.values["has_summary"] == 0.0

    def test_engagement_dwell_seconds(self) -> None:
        f = extract_features(
            published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            engagement=EngagementStats(ctr=0.1, avg_dwell_ms=30000),
        )
        assert f.values["dwell_time"] == 30.0
        assert f.values["ctr"] == 0.1

    def test_default_values(self) -> None:
        f = extract_features(published_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
        assert f.values["cf_score"] == 0.0
        assert f.values["fatigue_penalty"] == 0.0
        assert f.values["category_weight"] == 1.0


class TestLTRModel:
    def test_unloaded_model_returns_none(self) -> None:
        model = LTRModel()
        assert not model.is_loaded
        features = LTRFeatures(values={n: 0.0 for n in FEATURE_NAMES})
        assert model.predict(features) is None

    def test_load_nonexistent_path_stays_unloaded(self) -> None:
        model = LTRModel()
        model.load("/nonexistent/path/model.pkl")
        assert not model.is_loaded


class TestFallback:
    def test_fallback_to_rule_based_when_no_model(self) -> None:
        features = extract_features(
            published_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            category="it",
            source_type="news",
            article_count=3,
            now=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
        )
        score_input = ScoreInput(
            published_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            category="it",
            source_type="news",
            article_count=3,
        )
        model = LTRModel()  # No model loaded
        result = ltr_score_or_fallback(features, score_input, model=model)
        assert result > 0  # rule-based should give positive score
