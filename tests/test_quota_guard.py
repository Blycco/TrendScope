"""Tests for backend.crawler.quota_guard."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from backend.crawler.quota_guard import check_quota, increment_quota, reset_all_quotas


def _make_pool(row: dict | None = None, execute_return: str = "UPDATE 1") -> MagicMock:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=row)
    pool.execute = AsyncMock(return_value=execute_return)
    return pool


class TestCheckQuota:
    async def test_source_not_found_returns_false(self) -> None:
        pool = _make_pool(row=None)
        assert await check_quota("missing", pool) is False

    async def test_disabled_source_returns_false(self) -> None:
        row = {"is_active": False, "quota_limit": 100, "quota_used": 0}
        pool = _make_pool(row=row)
        assert await check_quota("disabled_src", pool) is False

    async def test_unlimited_quota_returns_true(self) -> None:
        row = {"is_active": True, "quota_limit": 0, "quota_used": 9999}
        pool = _make_pool(row=row)
        assert await check_quota("unlimited_src", pool) is True

    async def test_under_quota_returns_true(self) -> None:
        row = {"is_active": True, "quota_limit": 100, "quota_used": 50}
        pool = _make_pool(row=row)
        assert await check_quota("src", pool) is True

    async def test_at_limit_returns_false(self) -> None:
        row = {"is_active": True, "quota_limit": 100, "quota_used": 100}
        pool = _make_pool(row=row)
        assert await check_quota("src", pool) is False

    async def test_over_limit_returns_false(self) -> None:
        row = {"is_active": True, "quota_limit": 100, "quota_used": 101}
        pool = _make_pool(row=row)
        assert await check_quota("src", pool) is False

    async def test_db_error_returns_false(self) -> None:
        pool = MagicMock()
        pool.fetchrow = AsyncMock(side_effect=RuntimeError("DB error"))
        assert await check_quota("src", pool) is False

    async def test_exactly_one_under_limit(self) -> None:
        row = {"is_active": True, "quota_limit": 100, "quota_used": 99}
        pool = _make_pool(row=row)
        assert await check_quota("src", pool) is True


class TestIncrementQuota:
    async def test_increment_calls_execute(self) -> None:
        pool = _make_pool()
        await increment_quota("reddit", pool)
        pool.execute.assert_awaited_once()
        call_args = pool.execute.call_args[0]
        assert "$1" in call_args[0]
        assert call_args[1] == "reddit"

    async def test_increment_on_db_error_does_not_raise(self) -> None:
        pool = MagicMock()
        pool.execute = AsyncMock(side_effect=RuntimeError("DB down"))
        await increment_quota("src", pool)  # should not raise


class TestResetAllQuotas:
    async def test_reset_calls_execute(self) -> None:
        pool = _make_pool()
        await reset_all_quotas(pool)
        pool.execute.assert_awaited_once()

    async def test_reset_on_db_error_does_not_raise(self) -> None:
        pool = MagicMock()
        pool.execute = AsyncMock(side_effect=RuntimeError("DB error"))
        await reset_all_quotas(pool)  # should not raise
