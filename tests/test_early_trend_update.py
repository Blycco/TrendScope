"""Tests for backend.jobs.early_trend_update."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

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
) -> MagicMock:
    """Create a mock group row."""
    now = datetime.now(tz=timezone.utc)
    row = MagicMock()
    data = {
        "id": uuid.uuid4(),
        "article_count": article_count,
        "unique_sources": unique_sources,
        "newest_publish_time": now - timedelta(hours=hours_ago),
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


class TestRunEarlyTrendUpdate:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_groups(self) -> None:
        pool = _make_pool(groups=[])
        result = await run_early_trend_update(pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_updates_groups_and_returns_count(self) -> None:
        rows = [_make_group_row(article_count=5, unique_sources=3, hours_ago=2.0)]
        pool = _make_pool(groups=rows)
        result = await run_early_trend_update(pool)
        assert result == 1

    @pytest.mark.asyncio
    async def test_score_calculation_velocity(self) -> None:
        """10+ articles should give velocity = 1.0."""
        rows = [_make_group_row(article_count=15, unique_sources=5, hours_ago=0.0)]
        pool = _make_pool(groups=rows)

        await run_early_trend_update(pool)

        # Verify the UPDATE was called
        ctx = pool.acquire.return_value
        conn = await ctx.__aenter__()
        assert conn.execute.called
        call_args = conn.execute.call_args_list[-1]
        score = call_args[0][1]
        # velocity=1.0, diversity=5/15≈0.33, recency=1.0
        # 0.4*1.0 + 0.3*0.33 + 0.3*1.0 ≈ 0.7
        assert 0.6 < score < 0.85

    @pytest.mark.asyncio
    async def test_score_decreases_with_old_articles(self) -> None:
        """Articles from 40 hours ago should have low recency."""
        rows = [_make_group_row(article_count=5, unique_sources=3, hours_ago=40.0)]
        pool = _make_pool(groups=rows)

        await run_early_trend_update(pool)

        ctx = pool.acquire.return_value
        conn = await ctx.__aenter__()
        call_args = conn.execute.call_args_list[-1]
        score = call_args[0][1]
        # velocity=0.5, diversity=0.6, recency≈0.17
        # 0.4*0.5 + 0.3*0.6 + 0.3*0.17 ≈ 0.43
        assert score < 0.5

    @pytest.mark.asyncio
    async def test_handles_row_error_gracefully(self) -> None:
        """A bad row should not stop processing of other rows."""
        good_row = _make_group_row()
        bad_row = MagicMock()
        bad_row.__getitem__ = MagicMock(side_effect=KeyError("article_count"))

        pool = _make_pool(groups=[bad_row, good_row])
        result = await run_early_trend_update(pool)
        assert result == 1

    @pytest.mark.asyncio
    async def test_raises_on_db_connection_error(self) -> None:
        pool = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("connection refused"))
        ctx.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = ctx

        with pytest.raises(RuntimeError, match="connection refused"):
            await run_early_trend_update(pool)
