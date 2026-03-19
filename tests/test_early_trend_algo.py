"""Tests for backend/processor/algorithms/early_trend.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.burst import BurstLevel, BurstResult
from backend.processor.algorithms.early_trend import compute_early_trend_score


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
    """Return cached bytes for default weights (0.5, 0.3, 0.2)."""
    return json.dumps({"burst": 0.5, "velocity": 0.3, "diversity": 0.2}).encode()


class TestComputeEarlyTrendScore:
    @pytest.mark.asyncio
    async def test_basic_weighted_formula(self) -> None:
        # 0.5*0.8 + 0.3*0.6 + 0.2*0.4 = 0.4 + 0.18 + 0.08 = 0.66
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(0.8), 0.6, 0.4)
        assert abs(result - 0.66) < 1e-9

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
            result = await compute_early_trend_score(_make_pool(), _burst(1.0), 1.0, 1.0)
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_negative_clamped_to_zero(self) -> None:
        # 0.5*(-0.5) + 0.3*(-0.5) + 0.2*(-0.5) = -0.5 → clamped to 0.0
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(-0.5), -0.5, -0.5)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_above_one_clamped_to_one(self) -> None:
        # 0.5*1.5 + 0.3*1.5 + 0.2*1.5 = 1.5 → clamped to 1.0
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(1.5), 1.5, 1.5)
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_burst_weight_dominates(self) -> None:
        # Only burst=1.0, rest=0: 0.5*1 + 0 + 0 = 0.5
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(1.0), 0.0, 0.0)
        assert abs(result - 0.5) < 1e-9

    @pytest.mark.asyncio
    async def test_velocity_weight_only(self) -> None:
        # Only velocity=1.0: 0 + 0.3*1 + 0 = 0.3
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(0.0), 1.0, 0.0)
        assert abs(result - 0.3) < 1e-9

    @pytest.mark.asyncio
    async def test_diversity_weight_only(self) -> None:
        # Only diversity=1.0: 0 + 0 + 0.2*1 = 0.2
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(_make_pool(), _burst(0.0), 0.0, 1.0)
        assert abs(result - 0.2) < 1e-9

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "burst_score, velocity, diversity, expected",
        [
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.5),
            (0.0, 1.0, 0.0, 0.3),
            (0.0, 0.0, 1.0, 0.2),
            (0.4, 0.4, 0.4, 0.4),
        ],
    )
    async def test_parametrize_combinations(
        self, burst_score: float, velocity: float, diversity: float, expected: float
    ) -> None:
        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=_default_weights_cache()),
        ):
            result = await compute_early_trend_score(
                _make_pool(), _burst(burst_score), velocity, diversity
            )
        assert abs(result - expected) < 1e-9
