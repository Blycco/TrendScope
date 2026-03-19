"""Tests for brand_monitor.py algorithm.

Coverage targets:
- calculate_zscore(): normal, zero std, negative z
- _compute_stats(): empty list, single value, variance
- monitor_brand(): cache hit, cache miss, crisis detection
- SentimentAnalyzer reuse via monitor_brand() text processing (mocked)
"""

from __future__ import annotations

import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.brand_monitor import (
    _compute_stats,
    calculate_zscore,
    monitor_brand,
)
from backend.processor.algorithms.sentiment import SentimentResult

# ---------------------------------------------------------------------------
# calculate_zscore
# ---------------------------------------------------------------------------


class TestCalculateZscore:
    def test_normal_positive_zscore(self) -> None:
        result = calculate_zscore(current_score=1.0, mean_24h=0.0, std_24h=0.5)
        assert result == pytest.approx(2.0)

    def test_normal_negative_zscore(self) -> None:
        result = calculate_zscore(current_score=-1.0, mean_24h=0.0, std_24h=0.5)
        assert result == pytest.approx(-2.0)

    def test_zero_std_returns_zero(self) -> None:
        result = calculate_zscore(current_score=5.0, mean_24h=2.0, std_24h=0.0)
        assert result == 0.0

    def test_score_equal_to_mean_returns_zero(self) -> None:
        result = calculate_zscore(current_score=0.5, mean_24h=0.5, std_24h=1.0)
        assert result == pytest.approx(0.0)

    def test_large_deviation(self) -> None:
        result = calculate_zscore(current_score=10.0, mean_24h=0.0, std_24h=2.0)
        assert result == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# _compute_stats
# ---------------------------------------------------------------------------


class TestComputeStats:
    def test_empty_returns_zeros(self) -> None:
        mean, std = _compute_stats([])
        assert mean == 0.0
        assert std == 0.0

    def test_single_value(self) -> None:
        mean, std = _compute_stats([3.0])
        assert mean == pytest.approx(3.0)
        assert std == pytest.approx(0.0)

    def test_known_values(self) -> None:
        scores = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        mean, std = _compute_stats(scores)
        assert mean == pytest.approx(5.0)
        assert std == pytest.approx(2.0)

    def test_all_same_values(self) -> None:
        mean, std = _compute_stats([1.0, 1.0, 1.0])
        assert mean == pytest.approx(1.0)
        assert std == pytest.approx(0.0)

    def test_negative_values(self) -> None:
        mean, std = _compute_stats([-1.0, 0.0, 1.0])
        assert mean == pytest.approx(0.0)
        assert std == pytest.approx(math.sqrt(2 / 3))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


# ---------------------------------------------------------------------------
# monitor_brand — cache hit
# ---------------------------------------------------------------------------


class TestMonitorBrandCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_true_on_hit(self) -> None:
        pool = _make_pool()
        cached_payload = json.dumps(
            {
                "brand_name": "TestBrand",
                "current_score": -0.5,
                "mean_24h": 0.1,
                "std_24h": 0.2,
                "z_score": -3.0,
                "alert_threshold": 2.0,
                "is_crisis": True,
                "label": "crisis",
                "mentions": [],
            }
        ).encode()

        with patch(
            "backend.processor.algorithms.brand_monitor.get_cached",
            new=AsyncMock(return_value=cached_payload),
        ):
            result = await monitor_brand(pool, "uid-1", "TestBrand", [])

        assert result.cached is True
        assert result.is_crisis is True
        assert result.label == "crisis"
        assert result.z_score == pytest.approx(-3.0)

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db_fetch(self) -> None:
        pool = _make_pool()
        cached_payload = json.dumps(
            {
                "brand_name": "X",
                "current_score": 0.0,
                "mean_24h": 0.0,
                "std_24h": 0.0,
                "z_score": 0.0,
                "alert_threshold": 2.0,
                "is_crisis": False,
                "label": "normal",
                "mentions": [],
            }
        ).encode()

        with patch(
            "backend.processor.algorithms.brand_monitor.get_cached",
            new=AsyncMock(return_value=cached_payload),
        ):
            await monitor_brand(pool, "uid-1", "X", [])

        pool.acquire.assert_not_called()


# ---------------------------------------------------------------------------
# monitor_brand — cache miss
# ---------------------------------------------------------------------------


class TestMonitorBrandCacheMiss:
    @pytest.mark.asyncio
    async def test_no_texts_returns_normal(self) -> None:
        pool = _make_pool()

        with (
            patch(
                "backend.processor.algorithms.brand_monitor.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor.set_cached",
                new=AsyncMock(),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_brand_record",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_alert_threshold",
                new=AsyncMock(return_value=2.0),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_recent_scores",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await monitor_brand(pool, "uid-1", "BrandX", [])

        assert result.cached is False
        assert result.label == "normal"
        assert result.z_score == pytest.approx(0.0)
        assert result.is_crisis is False

    @pytest.mark.asyncio
    async def test_positive_texts_returns_positive_score(self) -> None:
        """Mock _analyzer so sentiment is deterministic regardless of model."""
        pool = _make_pool()

        with (
            patch(
                "backend.processor.algorithms.brand_monitor.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor.set_cached",
                new=AsyncMock(),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_brand_record",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_alert_threshold",
                new=AsyncMock(return_value=2.0),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_recent_scores",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._analyzer",
                analyze=MagicMock(return_value=SentimentResult(label="positive", score=0.8)),
            ),
        ):
            result = await monitor_brand(pool, "uid-1", "BrandX", ["great success"])

        assert result.current_score > 0
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_crisis_detected_when_zscore_exceeds_threshold(self) -> None:
        """Mock _analyzer for deterministic negative score triggering crisis."""
        pool = _make_pool()
        # historical: mean≈0.5, std≈0.071 → current=-0.5 → z≈-14 >> 2.0
        historical = [0.4, 0.5, 0.5, 0.6]

        with (
            patch(
                "backend.processor.algorithms.brand_monitor.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor.set_cached",
                new=AsyncMock(),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_brand_record",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_alert_threshold",
                new=AsyncMock(return_value=2.0),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_recent_scores",
                new=AsyncMock(return_value=historical),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._analyzer",
                analyze=MagicMock(return_value=SentimentResult(label="negative", score=0.5)),
            ),
        ):
            result = await monitor_brand(
                pool,
                "uid-1",
                "BrandX",
                ["bad terrible"],
            )

        assert result.is_crisis is True
        assert result.label == "crisis"
        assert result.z_score < -2.0

    @pytest.mark.asyncio
    async def test_result_is_cached_after_miss(self) -> None:
        pool = _make_pool()
        mock_set = AsyncMock()

        with (
            patch(
                "backend.processor.algorithms.brand_monitor.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor.set_cached",
                new=mock_set,
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_brand_record",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_alert_threshold",
                new=AsyncMock(return_value=2.0),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_recent_scores",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await monitor_brand(pool, "uid-1", "BrandX", [])

        mock_set.assert_awaited_once()
        call_args = mock_set.call_args
        assert call_args[0][0] == "brand:uid-1:brandx"
        assert call_args[0][2] == 900  # TTL

    @pytest.mark.asyncio
    async def test_surge_label_when_positive_crisis(self) -> None:
        """Mock _analyzer for deterministic positive score triggering surge."""
        pool = _make_pool()
        # historical mean=-0.5, std≈0.071 → current=0.5 → z≈14 >> 2
        historical = [-0.6, -0.5, -0.5, -0.4]

        with (
            patch(
                "backend.processor.algorithms.brand_monitor.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor.set_cached",
                new=AsyncMock(),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_brand_record",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_alert_threshold",
                new=AsyncMock(return_value=2.0),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._fetch_recent_scores",
                new=AsyncMock(return_value=historical),
            ),
            patch(
                "backend.processor.algorithms.brand_monitor._analyzer",
                analyze=MagicMock(return_value=SentimentResult(label="positive", score=0.8)),
            ),
        ):
            result = await monitor_brand(
                pool,
                "uid-1",
                "BrandX",
                ["great excellent success"],
            )

        assert result.is_crisis is True
        assert result.label == "surge"
