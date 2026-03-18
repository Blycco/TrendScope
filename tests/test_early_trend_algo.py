"""Tests for backend/processor/algorithms/early_trend.py."""

from __future__ import annotations

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


class TestComputeEarlyTrendScore:
    def test_basic_weighted_formula(self) -> None:
        # 0.5*0.8 + 0.3*0.6 + 0.2*0.4 = 0.4 + 0.18 + 0.08 = 0.66
        result = compute_early_trend_score(_burst(0.8), 0.6, 0.4)
        assert abs(result - 0.66) < 1e-9

    def test_all_zeros_returns_zero(self) -> None:
        result = compute_early_trend_score(_burst(0.0), 0.0, 0.0)
        assert result == 0.0

    def test_all_ones_returns_one(self) -> None:
        result = compute_early_trend_score(_burst(1.0), 1.0, 1.0)
        assert result == 1.0

    def test_negative_clamped_to_zero(self) -> None:
        # 0.5*(-0.5) + 0.3*(-0.5) + 0.2*(-0.5) = -0.5 → clamped to 0.0
        result = compute_early_trend_score(_burst(-0.5), -0.5, -0.5)
        assert result == 0.0

    def test_above_one_clamped_to_one(self) -> None:
        # 0.5*1.5 + 0.3*1.5 + 0.2*1.5 = 1.5 → clamped to 1.0
        result = compute_early_trend_score(_burst(1.5), 1.5, 1.5)
        assert result == 1.0

    def test_burst_weight_dominates(self) -> None:
        # Only burst=1.0, rest=0: 0.5*1 + 0 + 0 = 0.5
        result = compute_early_trend_score(_burst(1.0), 0.0, 0.0)
        assert abs(result - 0.5) < 1e-9

    def test_velocity_weight_only(self) -> None:
        # Only velocity=1.0: 0 + 0.3*1 + 0 = 0.3
        result = compute_early_trend_score(_burst(0.0), 1.0, 0.0)
        assert abs(result - 0.3) < 1e-9

    def test_diversity_weight_only(self) -> None:
        # Only diversity=1.0: 0 + 0 + 0.2*1 = 0.2
        result = compute_early_trend_score(_burst(0.0), 0.0, 1.0)
        assert abs(result - 0.2) < 1e-9

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
    def test_parametrize_combinations(
        self, burst_score: float, velocity: float, diversity: float, expected: float
    ) -> None:
        result = compute_early_trend_score(_burst(burst_score), velocity, diversity)
        assert abs(result - expected) < 1e-9
