"""Tests for early_trend.py after admin_settings weight migration.

Coverage targets:
- _load_weights(): cache hit, DB fetch, fallback on error
- compute_early_trend_score(): basic formula, clamping, fallback on error
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.burst import BurstLevel, BurstResult
from backend.processor.algorithms.early_trend import _load_weights, compute_early_trend_score

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _burst(score: float) -> BurstResult:
    return BurstResult(
        score=score,
        level=BurstLevel.NORMAL,
        prophet_score=score,
        iforest_score=score,
        cusum_score=score,
    )


def _make_pool(rows: list | None = None) -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows or [])
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


def _make_db_rows() -> list:
    """Simulate asyncpg records as dicts with key/value."""
    return [
        {"key": "early_trend_w_burst", "value": '"0.6"'},
        {"key": "early_trend_w_velocity", "value": '"0.25"'},
        {"key": "early_trend_w_diversity", "value": '"0.10"'},
        {"key": "early_trend_w_recency", "value": '"0.05"'},
    ]


# ---------------------------------------------------------------------------
# _load_weights() — cache hit
# ---------------------------------------------------------------------------


class TestLoadWeightsCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_weights(self) -> None:
        pool = _make_pool()
        cached = json.dumps(
            {"burst": 0.6, "velocity": 0.25, "diversity": 0.10, "recency": 0.05}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            burst, velocity, diversity, recency = await _load_weights(pool)

        assert burst == 0.6
        assert velocity == 0.25
        assert diversity == 0.10
        assert recency == 0.05

    @pytest.mark.asyncio
    async def test_cache_hit_without_recency_uses_default(self) -> None:
        pool = _make_pool()
        cached = json.dumps({"burst": 0.5, "velocity": 0.3, "diversity": 0.2}).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            burst, velocity, diversity, recency = await _load_weights(pool)

        assert recency == 0.2  # default

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self) -> None:
        pool = _make_pool()
        cached = json.dumps(
            {"burst": 0.3, "velocity": 0.3, "diversity": 0.2, "recency": 0.2}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            await _load_weights(pool)

        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetch.assert_not_awaited()


# ---------------------------------------------------------------------------
# _load_weights() — DB fetch
# ---------------------------------------------------------------------------


class TestLoadWeightsDBFetch:
    @pytest.mark.asyncio
    async def test_loads_from_db_on_cache_miss(self) -> None:
        pool = _make_pool(rows=_make_db_rows())

        with (
            patch(
                "backend.processor.algorithms.early_trend.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.early_trend.set_cached",
                new=AsyncMock(),
            ),
        ):
            burst, velocity, diversity, recency = await _load_weights(pool)

        assert burst == 0.6
        assert velocity == 0.25
        assert diversity == 0.10
        assert recency == 0.05

    @pytest.mark.asyncio
    async def test_db_fetch_stores_in_cache(self) -> None:
        pool = _make_pool(rows=_make_db_rows())
        set_cached_mock = AsyncMock()

        with (
            patch(
                "backend.processor.algorithms.early_trend.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.early_trend.set_cached",
                new=set_cached_mock,
            ),
        ):
            await _load_weights(pool)

        set_cached_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_defaults_on_db_error(self) -> None:
        pool = _make_pool()
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(side_effect=Exception("DB error"))

        with (
            patch(
                "backend.processor.algorithms.early_trend.get_cached",
                new=AsyncMock(return_value=None),
            ),
        ):
            burst, velocity, diversity, recency = await _load_weights(pool)

        assert burst == 0.3
        assert velocity == 0.3
        assert diversity == 0.2
        assert recency == 0.2


# ---------------------------------------------------------------------------
# compute_early_trend_score()
# ---------------------------------------------------------------------------


class TestComputeEarlyTrendScore:
    @pytest.mark.asyncio
    async def test_basic_weighted_formula(self) -> None:
        pool = _make_pool()
        # 0.3*0.8 + 0.3*0.6 + 0.2*0.4 + 0.2*0.5 = 0.24+0.18+0.08+0.10 = 0.60
        cached = json.dumps(
            {"burst": 0.3, "velocity": 0.3, "diversity": 0.2, "recency": 0.2}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            result = await compute_early_trend_score(pool, _burst(0.8), 0.6, 0.4, recency=0.5)

        assert abs(result - 0.60) < 1e-9

    @pytest.mark.asyncio
    async def test_all_zeros_returns_zero(self) -> None:
        pool = _make_pool()
        cached = json.dumps(
            {"burst": 0.3, "velocity": 0.3, "diversity": 0.2, "recency": 0.2}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            result = await compute_early_trend_score(pool, _burst(0.0), 0.0, 0.0)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_all_ones_returns_one(self) -> None:
        pool = _make_pool()
        cached = json.dumps(
            {"burst": 0.3, "velocity": 0.3, "diversity": 0.2, "recency": 0.2}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            result = await compute_early_trend_score(pool, _burst(1.0), 1.0, 1.0, recency=1.0)

        assert result == 1.0

    @pytest.mark.asyncio
    async def test_negative_clamped_to_zero(self) -> None:
        pool = _make_pool()
        cached = json.dumps(
            {"burst": 0.3, "velocity": 0.3, "diversity": 0.2, "recency": 0.2}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            result = await compute_early_trend_score(pool, _burst(-0.5), -0.5, -0.5, recency=-0.5)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_above_one_clamped_to_one(self) -> None:
        pool = _make_pool()
        cached = json.dumps(
            {"burst": 0.3, "velocity": 0.3, "diversity": 0.2, "recency": 0.2}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            result = await compute_early_trend_score(pool, _burst(1.5), 1.5, 1.5, recency=1.5)

        assert result == 1.0

    @pytest.mark.asyncio
    async def test_custom_weights_from_db(self) -> None:
        pool = _make_pool()
        # Custom: burst=0.6, velocity=0.2, diversity=0.1, recency=0.1
        # 0.6*1.0 + 0.2*0.0 + 0.1*0.0 + 0.1*0.0 = 0.6
        cached = json.dumps(
            {"burst": 0.6, "velocity": 0.2, "diversity": 0.1, "recency": 0.1}
        ).encode()

        with patch(
            "backend.processor.algorithms.early_trend.get_cached",
            new=AsyncMock(return_value=cached),
        ):
            result = await compute_early_trend_score(pool, _burst(1.0), 0.0, 0.0)

        assert abs(result - 0.6) < 1e-9
