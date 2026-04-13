"""Tests for backend.jobs.early_trend_update."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.jobs.early_trend_update import run_early_trend_update


def _make_pool(
    groups: list[dict] | None = None,
    execute_result: str = "UPDATE 1",
) -> MagicMock:
    """Create a mock asyncpg pool with configurable fetch results."""
    pool = MagicMock()

    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=groups or [])
    mock_conn.execute = AsyncMock(return_value=execute_result)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx

    return pool


def _make_group_row(
    article_count: int = 5,
    unique_sources: int = 3,
    hours_ago: float = 2.0,
    burst_score: float = 0.0,
    cnt_1h: int = 0,
    cnt_24h: int | None = None,
) -> MagicMock:
    """Create a mock group row with time-window counts."""
    now = datetime.now(tz=timezone.utc)
    row = MagicMock()
    data = {
        "id": uuid.uuid4(),
        "burst_score": burst_score,
        "keywords": ["테스트", "키워드"],
        "locale": "ko",
        "article_count": article_count,
        "unique_sources": unique_sources,
        "newest_publish_time": now - timedelta(hours=hours_ago),
        "cnt_1h": cnt_1h,
        "cnt_24h": cnt_24h if cnt_24h is not None else article_count,
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


@patch(
    "backend.jobs.early_trend_update.verify_external_trends",
    new_callable=AsyncMock,
    return_value=1.0,
)
class TestRunEarlyTrendUpdate:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_groups(self, _mock_ext: AsyncMock) -> None:
        pool = _make_pool(groups=[])
        result = await run_early_trend_update(pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_updates_groups_and_returns_count(self, _mock_ext: AsyncMock) -> None:
        rows = [
            _make_group_row(
                article_count=5,
                unique_sources=3,
                hours_ago=2.0,
                cnt_1h=3,
                cnt_24h=5,
            )
        ]
        pool = _make_pool(groups=rows)
        result = await run_early_trend_update(pool)
        assert result == 1

    @pytest.mark.asyncio
    async def test_momentum_velocity_high_acceleration(self, _mock_ext: AsyncMock) -> None:
        """High recent activity relative to 24h average → high velocity."""
        rows = [
            _make_group_row(
                article_count=15,
                unique_sources=5,
                hours_ago=0.0,
                cnt_1h=5,
                cnt_24h=10,
                burst_score=0.5,
            )
        ]
        pool = _make_pool(groups=rows)

        await run_early_trend_update(pool)

        ctx = pool.acquire.return_value
        conn = await ctx.__aenter__()
        assert conn.execute.called
        call_args = conn.execute.call_args_list[-1]
        score = call_args[0][1]
        # hourly_avg=10/24≈0.42, acceleration=5/0.42≈12, velocity=min(1,12/5)=1.0
        # 0.3*1.0 + 0.25*0.5 + 0.25*(5/15) + 0.2*1.0 = 0.3+0.125+0.083+0.2=0.708
        assert 0.6 < score < 0.85

    @pytest.mark.asyncio
    async def test_score_decreases_with_old_articles(self, _mock_ext: AsyncMock) -> None:
        """Articles from 40 hours ago should have low recency."""
        rows = [
            _make_group_row(
                article_count=5,
                unique_sources=3,
                hours_ago=40.0,
                cnt_1h=0,
                cnt_24h=2,
            )
        ]
        pool = _make_pool(groups=rows)

        await run_early_trend_update(pool)

        ctx = pool.acquire.return_value
        conn = await ctx.__aenter__()
        call_args = conn.execute.call_args_list[-1]
        score = call_args[0][1]
        # velocity=0 (cnt_1h=0), burst=0, diversity=0.6, recency≈0.17
        # 0.3*0 + 0.25*0 + 0.25*0.6 + 0.2*0.17 = 0.15+0.034 = 0.184
        assert score < 0.3

    @pytest.mark.asyncio
    async def test_single_source_returns_zero(self, _mock_ext: AsyncMock) -> None:
        """Single source cluster should get score 0."""
        rows = [
            _make_group_row(
                article_count=5,
                unique_sources=1,
                hours_ago=0.0,
                cnt_1h=5,
                cnt_24h=5,
            )
        ]
        pool = _make_pool(groups=rows)

        await run_early_trend_update(pool)

        ctx = pool.acquire.return_value
        conn = await ctx.__aenter__()
        call_args = conn.execute.call_args_list[-1]
        score = call_args[0][1]
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_small_cluster_capped(self, _mock_ext: AsyncMock) -> None:
        """Clusters with <3 articles should be capped at 0.3."""
        rows = [
            _make_group_row(
                article_count=2,
                unique_sources=2,
                hours_ago=0.0,
                cnt_1h=2,
                cnt_24h=2,
                burst_score=1.0,
            )
        ]
        pool = _make_pool(groups=rows)

        await run_early_trend_update(pool)

        ctx = pool.acquire.return_value
        conn = await ctx.__aenter__()
        call_args = conn.execute.call_args_list[-1]
        score = call_args[0][1]
        assert score <= 0.3

    @pytest.mark.asyncio
    async def test_handles_row_error_gracefully(self, _mock_ext: AsyncMock) -> None:
        """A bad row should not stop processing of other rows."""
        good_row = _make_group_row(cnt_1h=2, cnt_24h=5)
        bad_row = MagicMock()
        bad_row.__getitem__ = MagicMock(side_effect=KeyError("article_count"))

        pool = _make_pool(groups=[bad_row, good_row])
        result = await run_early_trend_update(pool)
        assert result == 1

    @pytest.mark.asyncio
    async def test_raises_on_db_connection_error(self, _mock_ext: AsyncMock) -> None:
        pool = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("connection refused"))
        ctx.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = ctx

        with pytest.raises(RuntimeError, match="connection refused"):
            await run_early_trend_update(pool)
