"""Unit tests for backend/db/queries/trends.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.db.queries.trends import (
    decode_cursor,
    encode_cursor,
    fetch_early_trends,
    fetch_news,
    fetch_trends,
)

# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------


class TestCursor:
    def test_encode_decode_roundtrip(self) -> None:
        score = 0.87654
        row_id = "00000000-0000-0000-0000-000000000001"
        cursor = encode_cursor(score, row_id)
        decoded_score, decoded_id = decode_cursor(cursor)
        assert abs(decoded_score - score) < 1e-10
        assert decoded_id == row_id

    def test_encode_produces_url_safe_string(self) -> None:
        cursor = encode_cursor(1.0, "abc-123")
        assert "+" not in cursor
        assert "/" not in cursor

    def test_decode_invalid_raises(self) -> None:
        with pytest.raises((ValueError, Exception)):  # noqa: B017
            decode_cursor("not-valid-base64!!!")


# ---------------------------------------------------------------------------
# fetch_trends
# ---------------------------------------------------------------------------


def _make_pool(rows: list) -> MagicMock:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


class TestFetchTrends:
    async def test_no_filters(self) -> None:
        pool = _make_pool([])
        result = await fetch_trends(pool, category=None, locale=None)
        assert result == []

    async def test_category_filter(self) -> None:
        pool = _make_pool([])
        result = await fetch_trends(pool, category="tech", locale=None)
        assert result == []

    async def test_locale_filter(self) -> None:
        pool = _make_pool([])
        result = await fetch_trends(pool, category=None, locale="ko")
        assert result == []

    async def test_both_filters(self) -> None:
        pool = _make_pool([])
        result = await fetch_trends(pool, category="finance", locale="en")
        assert result == []

    async def test_with_cursor(self) -> None:
        pool = _make_pool([])
        cursor = encode_cursor(0.5, "00000000-0000-0000-0000-000000000001")
        result = await fetch_trends(pool, category=None, locale=None, cursor=cursor)
        assert result == []

    async def test_db_error_propagates(self) -> None:
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("DB 오류"))
        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        with pytest.raises(RuntimeError):
            await fetch_trends(pool, category=None, locale=None)


# ---------------------------------------------------------------------------
# fetch_early_trends
# ---------------------------------------------------------------------------


class TestFetchEarlyTrends:
    async def test_no_locale(self) -> None:
        pool = _make_pool([])
        result = await fetch_early_trends(pool, locale=None)
        assert result == []

    async def test_with_locale(self) -> None:
        pool = _make_pool([])
        result = await fetch_early_trends(pool, locale="ko")
        assert result == []

    async def test_with_cursor(self) -> None:
        pool = _make_pool([])
        cursor = encode_cursor(0.8, "00000000-0000-0000-0000-000000000002")
        result = await fetch_early_trends(pool, locale=None, cursor=cursor)
        assert result == []

    async def test_db_error_propagates(self) -> None:
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("timeout"))
        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        with pytest.raises(RuntimeError):
            await fetch_early_trends(pool, locale=None)


# ---------------------------------------------------------------------------
# fetch_news
# ---------------------------------------------------------------------------


class TestFetchNews:
    async def test_no_filters(self) -> None:
        pool = _make_pool([])
        result = await fetch_news(pool, category=None, locale=None)
        assert result == []

    async def test_category_and_locale(self) -> None:
        pool = _make_pool([])
        result = await fetch_news(pool, category="tech", locale="ko")
        assert result == []

    async def test_with_cursor(self) -> None:
        pool = _make_pool([])
        ts = datetime(2026, 3, 17, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        cursor = encode_cursor(ts, "00000000-0000-0000-0000-000000000003")
        result = await fetch_news(pool, category=None, locale=None, cursor=cursor)
        assert result == []

    async def test_db_error_propagates(self) -> None:
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=Exception("연결 실패"))
        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        with pytest.raises((Exception,)):  # noqa: B017
            await fetch_news(pool, category=None, locale=None)
