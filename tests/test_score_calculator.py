"""Tests for score_calculator module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from backend.processor.shared.score_calculator import (
    ScoreInput,
    ScoreResult,
    calculate_score,
    compute_freshness,
)


class TestComputeFreshness:
    """Tests for compute_freshness function."""

    def test_just_published(self) -> None:
        now = datetime.now(timezone.utc)
        score = compute_freshness(now, "default", now)
        assert score == pytest.approx(100.0, abs=0.01)

    def test_decays_over_time(self) -> None:
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=30)
        score = compute_freshness(past, "default", now)
        assert 0 < score < 100

    def test_breaking_decays_fastest(self) -> None:
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=60)
        breaking = compute_freshness(past, "breaking", now)
        it_score = compute_freshness(past, "it", now)
        assert breaking < it_score  # breaking lambda=0.10 > it lambda=0.02

    def test_it_decays_slowest(self) -> None:
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=120)
        it_score = compute_freshness(past, "it", now)
        politics = compute_freshness(past, "politics", now)
        assert it_score > politics  # it lambda=0.02 < politics lambda=0.04

    def test_unknown_category_uses_default(self) -> None:
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=60)
        unknown = compute_freshness(past, "unknown_category", now)
        default = compute_freshness(past, "default", now)
        assert unknown == pytest.approx(default, abs=0.001)

    def test_future_published_at_clamps(self) -> None:
        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=10)
        score = compute_freshness(future, "default", now)
        assert score == pytest.approx(100.0, abs=0.01)

    def test_naive_datetime_treated_as_utc(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        past = datetime(2025, 1, 1, 11, 0, 0)
        score = compute_freshness(past, "default", now)
        assert 0 < score < 100


class TestCalculateScore:
    """Tests for calculate_score function."""

    def test_basic_score(self) -> None:
        now = datetime.now(timezone.utc)
        inp = ScoreInput(published_at=now, category="default", source_type="news")
        result = calculate_score(inp, now)
        assert isinstance(result, ScoreResult)
        assert result.total > 0

    def test_score_components_sum(self) -> None:
        now = datetime.now(timezone.utc)
        inp = ScoreInput(
            published_at=now,
            category="default",
            source_type="news",
            article_count=5,
            social_signal=10.0,
            keyword_importance=5.0,
        )
        result = calculate_score(inp, now)
        expected = (
            result.freshness
            + result.source_weight
            + result.article_count_bonus
            + result.social_signal
            + result.keyword_importance
        )
        assert result.total == pytest.approx(expected, abs=0.001)

    def test_major_news_higher_weight(self) -> None:
        now = datetime.now(timezone.utc)
        major = calculate_score(ScoreInput(published_at=now, source_type="major_news"), now)
        blog = calculate_score(ScoreInput(published_at=now, source_type="blog"), now)
        assert major.source_weight > blog.source_weight

    def test_article_count_bonus(self) -> None:
        now = datetime.now(timezone.utc)
        single = calculate_score(ScoreInput(published_at=now, article_count=1), now)
        many = calculate_score(ScoreInput(published_at=now, article_count=100), now)
        assert many.article_count_bonus > single.article_count_bonus

    def test_article_count_bonus_capped(self) -> None:
        now = datetime.now(timezone.utc)
        huge = calculate_score(ScoreInput(published_at=now, article_count=1_000_000), now)
        assert huge.article_count_bonus <= 20.0

    def test_negative_social_signal_clamped(self) -> None:
        now = datetime.now(timezone.utc)
        result = calculate_score(
            ScoreInput(published_at=now, social_signal=-10.0),
            now,
        )
        assert result.social_signal == 0.0
