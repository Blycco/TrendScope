"""Tests for backend/processor/algorithms/early_trend.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.burst import BurstLevel, BurstResult
from backend.processor.algorithms.early_trend import (
    compute_early_trend_score,
    compute_momentum_velocity,
)


def _burst(score: float) -> BurstResult:
    return BurstResult(
        score=score,
        level=BurstLevel.NORMAL,
        prophet_score=score,
        iforest_score=score,
        cusum_score=score,
    )


def _make_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


def _default_weights_cache() -> bytes:
    """Return cached bytes for default weights (0.3, 0.3, 0.2, 0.2)."""
    return json.dumps({"burst": 0.3, "velocity": 0.3, "diversity": 0.2, "recency": 0.2}).encode()


class TestComputeMomentumVelocity:
    def test_zero_activity(self) -> None:
        assert compute_momentum_velocity(0, 0, 0) == 0.0

    def test_15m_boost(self) -> None:
        # cnt_15m=5, cnt_1h=5, cnt_24h=24 → weighted=10+0=10, avg=1.0, accel=10, vel=1.0
        result = compute_momentum_velocity(5, 5, 24)
        assert result == 1.0

    def test_no_15m_activity(self) -> None:
        # cnt_15m=0, cnt_1h=5, cnt_24h=24 → weighted=0+5=5, avg=1.0, accel=5, vel=1.0
        result = compute_momentum_velocity(0, 5, 24)
        assert result == 1.0

    def test_moderate_acceleration(self) -> None:
        # cnt_15m=1, cnt_1h=2, cnt_24h=24 → weighted=2+1=3, avg=1.0, accel=3, vel=0.6
        result = compute_momentum_velocity(1, 2, 24)
        assert abs(result - 0.6) < 1e-9

    def test_low_24h_uses_min_avg(self) -> None:
        # cnt_15m=1, cnt_1h=1, cnt_24h=0 → weighted=2+0=2, avg=0.1(floor), accel=20, vel=1.0
        result = compute_momentum_velocity(1, 1, 0)
        assert result == 1.0

    def test_custom_divisor(self) -> None:
        # cnt_15m=1, cnt_1h=2, cnt_24h=24 → weighted=3, avg=1.0, accel=3, vel=3/10=0.3
        result = compute_momentum_velocity(1, 2, 24, acceleration_divisor=10.0)
        assert abs(result - 0.3) < 1e-9

    def test_capped_at_one(self) -> None:
        # Very high acceleration → still capped at 1.0
        result = compute_momentum_velocity(100, 100, 1)
        assert result == 1.0


class TestComputeEarlyTrendScore:
    @pytest.mark.asyncio
    async def test_basic_weighted_formula(self) -> None:
        # 0.3*0.8 + 0.3*0.6 + 0.2*0.4 + 0.2*0.5 = 0.24+0.18+0.08+0.10 = 0.60
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(
                _make_pool(), _burst(0.8), 0.6, 0.4, recency=0.5
            )
        assert abs(result - 0.60) < 1e-9

    @pytest.mark.asyncio
    async def test_all_zeros_returns_zero(self) -> None:
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(0.0), 0.0, 0.0)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_all_ones_returns_one(self) -> None:
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(
                _make_pool(), _burst(1.0), 1.0, 1.0, recency=1.0
            )
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_negative_clamped_to_zero(self) -> None:
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(
                _make_pool(), _burst(-0.5), -0.5, -0.5, recency=-0.5
            )
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_above_one_clamped_to_one(self) -> None:
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(
                _make_pool(), _burst(1.5), 1.5, 1.5, recency=1.5
            )
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_burst_weight_only(self) -> None:
        # Only burst=1.0, rest=0: 0.3*1 = 0.3
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(1.0), 0.0, 0.0)
        assert abs(result - 0.3) < 1e-9

    @pytest.mark.asyncio
    async def test_velocity_weight_only(self) -> None:
        # Only velocity=1.0: 0.3*1 = 0.3
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(0.0), 1.0, 0.0)
        assert abs(result - 0.3) < 1e-9

    @pytest.mark.asyncio
    async def test_recency_weight_only(self) -> None:
        # Only recency=1.0: 0.2*1 = 0.2
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(
                _make_pool(), _burst(0.0), 0.0, 0.0, recency=1.0
            )
        assert abs(result - 0.2) < 1e-9

    @pytest.mark.asyncio
    async def test_accepts_raw_float_burst(self) -> None:
        # Can pass float instead of BurstResult
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), 1.0, 0.0, 0.0)
        assert abs(result - 0.3) < 1e-9

    @pytest.mark.asyncio
    async def test_recency_default_zero(self) -> None:
        # Without recency param: 0.3*1 + 0.3*1 + 0.2*1 + 0.2*0 = 0.8
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(1.0), 1.0, 1.0)
        assert abs(result - 0.8) < 1e-9
