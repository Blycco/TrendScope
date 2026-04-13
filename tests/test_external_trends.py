"""Tests for backend.processor.algorithms.external_trends."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.processor.algorithms.external_trends import verify_external_trends


def _make_pool(platform_count: int = 0) -> MagicMock:
    """Create a mock pool that returns a given platform_count."""
    pool = MagicMock()
    mock_conn = MagicMock()

    row = {"platform_count": platform_count}
    mock_conn.fetchrow = AsyncMock(return_value=row)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx

    return pool


class TestVerifyExternalTrends:
    @pytest.mark.asyncio
    async def test_empty_keywords_returns_1(self) -> None:
        pool = _make_pool()
        result = await verify_external_trends(pool, [], locale="ko")
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_no_match_returns_1(self) -> None:
        pool = _make_pool(platform_count=0)
        result = await verify_external_trends(pool, ["AI", "인공지능"], locale="ko")
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_single_platform_match_returns_1_1(self) -> None:
        pool = _make_pool(platform_count=1)
        result = await verify_external_trends(pool, ["AI"], locale="ko")
        assert result == 1.1

    @pytest.mark.asyncio
    async def test_dual_platform_match_returns_1_3(self) -> None:
        pool = _make_pool(platform_count=2)
        result = await verify_external_trends(pool, ["AI"], locale="ko")
        assert result == 1.3

    @pytest.mark.asyncio
    async def test_more_than_2_platforms_capped_at_1_3(self) -> None:
        pool = _make_pool(platform_count=5)
        result = await verify_external_trends(pool, ["AI"], locale="ko")
        assert result == 1.3

    @pytest.mark.asyncio
    async def test_db_error_returns_1(self) -> None:
        pool = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("connection lost"))
        ctx.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = ctx

        result = await verify_external_trends(pool, ["AI"], locale="ko")
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_null_row_returns_1(self) -> None:
        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        ctx.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = ctx

        result = await verify_external_trends(pool, ["AI"], locale="ko")
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_query_uses_correct_parameters(self) -> None:
        pool = _make_pool(platform_count=1)
        await verify_external_trends(pool, ["AI", "ChatGPT"], locale="en")

        ctx = pool.acquire.return_value
        conn = await ctx.__aenter__()
        call_args = conn.fetchrow.call_args

        # Verify keywords, locale, and platforms are passed
        assert call_args[0][1] == ["AI", "ChatGPT"]
        assert call_args[0][2] == "en"
        assert "google_trends" in call_args[0][3]
        assert "naver_datalab" in call_args[0][3]
