"""Tests for growth_type classification wired into stage_score."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from backend.processor.stages.score import _build_velocity_windows


def _article(hours_ago: float) -> dict:
    return {"publish_time": datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago)}


class TestBuildVelocityWindows:
    def test_buckets_articles_by_12h_windows(self) -> None:
        articles = [
            _article(1),  # window 0
            _article(2),  # window 0
            _article(15),  # window 1
            _article(30),  # window 2
        ]
        windows = _build_velocity_windows(articles)

        assert len(windows) == 3
        assert windows[0].article_count == 2
        assert windows[1].article_count == 1
        assert windows[2].article_count == 1
        assert windows[0].window_start_hours_ago == 0
        assert windows[0].window_end_hours_ago == 12

    def test_empty_articles_returns_zero_buckets(self) -> None:
        windows = _build_velocity_windows([])
        assert [w.article_count for w in windows] == [0, 0, 0]

    def test_articles_beyond_window_ignored(self) -> None:
        articles = [_article(100)]  # outside 36h range
        windows = _build_velocity_windows(articles)
        assert all(w.article_count == 0 for w in windows)


class TestClassifyGrowthIntegration:
    def test_spike_pattern_detected(self) -> None:
        from backend.processor.algorithms.growth_classifier import classify_growth_type

        # 10 recent + 1 mid → spike
        articles = [_article(2)] * 10 + [_article(15)]
        windows = _build_velocity_windows(articles)
        assert classify_growth_type(windows).value == "spike"

    def test_growth_pattern_detected(self) -> None:
        from backend.processor.algorithms.growth_classifier import classify_growth_type

        # 12 recent, 10 mid, 8 old → growth (recent ≥ 1.2*mid, mid ≥ 1.1*old)
        articles = [_article(2)] * 12 + [_article(15)] * 10 + [_article(28)] * 8
        windows = _build_velocity_windows(articles)
        assert classify_growth_type(windows).value == "growth"

    def test_flat_pattern_unknown(self) -> None:
        from backend.processor.algorithms.growth_classifier import classify_growth_type

        articles = [_article(2)] * 5 + [_article(15)] * 5 + [_article(28)] * 5
        windows = _build_velocity_windows(articles)
        assert classify_growth_type(windows).value == "unknown"


@pytest.mark.asyncio
async def test_stage_save_persists_classified_growth_type() -> None:
    """End-to-end: a cluster with growth_type='spike' reaches the INSERT statement."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from backend.processor.stages import save as save_stage

    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[{"id": "gid-1"}])
    conn.executemany = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)

    cluster = {
        "category": "it",
        "locale": "ko",
        "title": "t",
        "summary": "s",
        "score": 50.0,
        "early_trend_score": 0.4,
        "keywords": ["a"],
        "burst_score": 0.3,
        "cross_platform_multiplier": 1.0,
        "external_trend_boost": 1.0,
        "growth_type": "spike",
        "articles": [],
    }
    with patch.object(save_stage, "publish", AsyncMock()):
        await save_stage.stage_save([cluster], pool)

    sql, *args = conn.fetch.await_args.args
    assert "growth_type" in sql
    assert args[10] == ["spike"]
