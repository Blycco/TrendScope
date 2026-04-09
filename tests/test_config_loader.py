"""Tests for backend/processor/shared/config_loader.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.shared.config_loader import (
    _cast,
    get_category_keywords,
    get_filter_keywords,
    get_setting,
    get_stopwords,
    invalidate_cache,
)


def _make_pool(fetchrow_return=None, fetch_return=None) -> MagicMock:
    """Build a minimal mock asyncpg pool."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


# ── _cast ────────────────────────────────────────────────────────────────────


class TestCast:
    def test_cast_to_float(self) -> None:
        assert _cast("0.35", 0.0) == pytest.approx(0.35)

    def test_cast_to_int(self) -> None:
        assert _cast("3", 0) == 3

    def test_cast_float_string_to_int(self) -> None:
        assert _cast("2.0", 0) == 2

    def test_cast_to_str(self) -> None:
        assert _cast("gemini-flash", "") == "gemini-flash"

    def test_cast_invalid_returns_default(self) -> None:
        assert _cast("not_a_number", 1.0) == 1.0

    def test_cast_invalid_int_returns_default(self) -> None:
        assert _cast("abc", 5) == 5


# ── get_setting ──────────────────────────────────────────────────────────────


class TestGetSetting:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_value(self) -> None:
        pool = _make_pool()
        with patch(
            "backend.processor.shared.config_loader.get_cached",
            AsyncMock(return_value=b"0.65"),
        ):
            result = await get_setting(pool, "cluster.threshold", 0.55)
        assert result == pytest.approx(0.65)

    @pytest.mark.asyncio
    async def test_cache_miss_loads_from_db(self) -> None:
        pool = _make_pool(fetchrow_return={"value": '"0.70"'})
        with (
            patch(
                "backend.processor.shared.config_loader.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.shared.config_loader.set_cached",
                AsyncMock(),
            ),
        ):
            result = await get_setting(pool, "cluster.louvain_threshold", 0.55)
        assert result == pytest.approx(0.70)

    @pytest.mark.asyncio
    async def test_key_not_found_returns_default(self) -> None:
        pool = _make_pool(fetchrow_return=None)
        with (
            patch(
                "backend.processor.shared.config_loader.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.shared.config_loader.set_cached",
                AsyncMock(),
            ),
        ):
            result = await get_setting(pool, "nonexistent.key", 42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_db_error_returns_default(self) -> None:
        pool = MagicMock()
        pool.acquire = MagicMock(side_effect=RuntimeError("DB down"))
        with patch(
            "backend.processor.shared.config_loader.get_cached",
            AsyncMock(return_value=None),
        ):
            result = await get_setting(pool, "cluster.threshold", 0.55)
        assert result == pytest.approx(0.55)


# ── get_stopwords ─────────────────────────────────────────────────────────────


class TestGetStopwords:
    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        pool = _make_pool()
        cached_words = json.dumps(["것이", "하는", "있는"]).encode()
        with patch(
            "backend.processor.shared.config_loader.get_cached",
            AsyncMock(return_value=cached_words),
        ):
            result = await get_stopwords(pool, "ko")
        assert "것이" in result
        assert "하는" in result
        assert isinstance(result, frozenset)

    @pytest.mark.asyncio
    async def test_cache_miss_loads_from_db(self) -> None:
        rows = [{"word": "1월"}, {"word": "12월"}, {"word": "분기"}]
        pool = _make_pool(fetch_return=rows)
        with (
            patch(
                "backend.processor.shared.config_loader.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.shared.config_loader.set_cached",
                AsyncMock(),
            ),
        ):
            result = await get_stopwords(pool, "ko")
        assert "1월" in result
        assert "12월" in result

    @pytest.mark.asyncio
    async def test_locale_separation(self) -> None:
        """ko와 en은 별도 캐시 키를 사용해야 한다."""
        calls: list[str] = []

        async def mock_get_cached(key: str) -> None:
            calls.append(key)
            return None

        pool = _make_pool(fetch_return=[])
        with (
            patch(
                "backend.processor.shared.config_loader.get_cached",
                mock_get_cached,
            ),
            patch(
                "backend.processor.shared.config_loader.set_cached",
                AsyncMock(),
            ),
        ):
            await get_stopwords(pool, "ko")
            await get_stopwords(pool, "en")

        ko_keys = [k for k in calls if "ko" in k]
        en_keys = [k for k in calls if "en" in k]
        assert len(ko_keys) >= 1
        assert len(en_keys) >= 1
        assert ko_keys[0] != en_keys[0]


# ── get_filter_keywords ───────────────────────────────────────────────────────


class TestGetFilterKeywords:
    @pytest.mark.asyncio
    async def test_category_filter(self) -> None:
        rows = [{"keyword": "부고"}, {"keyword": "서거"}, {"keyword": "별세"}]
        pool = _make_pool(fetch_return=rows)
        with (
            patch(
                "backend.processor.shared.config_loader.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.shared.config_loader.set_cached",
                AsyncMock(),
            ),
        ):
            result = await get_filter_keywords(pool, category="obituary")
        assert "부고" in result
        assert "서거" in result
        assert isinstance(result, frozenset)

    @pytest.mark.asyncio
    async def test_no_category_returns_all(self) -> None:
        rows = [{"keyword": "부고"}, {"keyword": "광고"}, {"keyword": "카지노"}]
        pool = _make_pool(fetch_return=rows)
        with (
            patch(
                "backend.processor.shared.config_loader.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.shared.config_loader.set_cached",
                AsyncMock(),
            ),
        ):
            result = await get_filter_keywords(pool)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_db_error_returns_empty_frozenset(self) -> None:
        pool = MagicMock()
        pool.acquire = MagicMock(side_effect=RuntimeError("DB down"))
        with patch(
            "backend.processor.shared.config_loader.get_cached",
            AsyncMock(return_value=None),
        ):
            result = await get_filter_keywords(pool, "obituary")
        assert result == frozenset()


# ── get_category_keywords ─────────────────────────────────────────────────────


class TestGetCategoryKeywords:
    @pytest.mark.asyncio
    async def test_groups_by_category(self) -> None:
        rows = [
            {"keyword": "축구", "category": "sports", "weight": 1.5},
            {"keyword": "야구", "category": "sports", "weight": 1.5},
            {"keyword": "반도체", "category": "tech", "weight": 1.5},
        ]
        pool = _make_pool(fetch_return=rows)
        with (
            patch(
                "backend.processor.shared.config_loader.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.shared.config_loader.set_cached",
                AsyncMock(),
            ),
        ):
            result = await get_category_keywords(pool)

        assert "sports" in result
        assert "tech" in result
        assert ("축구", 1.5) in result["sports"]
        assert ("반도체", 1.5) in result["tech"]


# ── invalidate_cache ──────────────────────────────────────────────────────────


class TestInvalidateCache:
    @pytest.mark.asyncio
    async def test_invalidate_specific_setting(self) -> None:
        deleted: list[str] = []

        async def mock_delete(key: str) -> None:
            deleted.append(key)

        with patch("backend.processor.shared.config_loader.delete_cached", mock_delete):
            await invalidate_cache("setting:cluster.threshold")

        assert any("cluster.threshold" in k for k in deleted)

    @pytest.mark.asyncio
    async def test_invalidate_stopwords_both_locales(self) -> None:
        deleted: list[str] = []

        async def mock_delete(key: str) -> None:
            deleted.append(key)

        with patch("backend.processor.shared.config_loader.delete_cached", mock_delete):
            await invalidate_cache("stopwords")

        ko_deleted = any("ko" in k for k in deleted)
        en_deleted = any("en" in k for k in deleted)
        assert ko_deleted
        assert en_deleted

    @pytest.mark.asyncio
    async def test_invalidate_filter_kw(self) -> None:
        deleted: list[str] = []

        async def mock_delete(key: str) -> None:
            deleted.append(key)

        with patch("backend.processor.shared.config_loader.delete_cached", mock_delete):
            await invalidate_cache("filter_kw")

        assert len(deleted) > 0

    @pytest.mark.asyncio
    async def test_invalidate_category_kw(self) -> None:
        deleted: list[str] = []

        async def mock_delete(key: str) -> None:
            deleted.append(key)

        with patch("backend.processor.shared.config_loader.delete_cached", mock_delete):
            await invalidate_cache("category_kw")

        assert len(deleted) == 1
