"""Tests for backend/api/middleware/quota.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.api.middleware.quota import check_insight_quota, increment_insight_usage
from backend.auth.dependencies import CurrentUser
from fastapi import HTTPException


def _make_user(plan: str = "free", user_id: str = "user-abc-123") -> CurrentUser:
    return CurrentUser(user_id=user_id, plan=plan, role="general")


def _make_pool(execute_return: object = None, fetchrow_return: object = None) -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=execute_return)
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


def _make_request(pool: MagicMock) -> MagicMock:
    request = MagicMock()
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.db_pool = pool
    return request


def _api_usage_row(used_count: int, quota_limit: int) -> dict:
    return {"used_count": used_count, "quota_limit": quota_limit}


class TestCheckInsightQuota:
    @pytest.mark.asyncio
    async def test_pro_plan_skips_quota_check(self) -> None:
        pool = _make_pool()
        user = _make_user(plan="pro")
        request = _make_request(pool)

        result = await check_insight_quota(request=request, current_user=user)

        assert result is user
        # Pool should not have been touched
        pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_business_plan_skips_quota_check(self) -> None:
        pool = _make_pool()
        user = _make_user(plan="business")
        request = _make_request(pool)

        result = await check_insight_quota(request=request, current_user=user)

        assert result is user
        pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_enterprise_plan_skips_quota_check(self) -> None:
        pool = _make_pool()
        user = _make_user(plan="enterprise")
        request = _make_request(pool)

        result = await check_insight_quota(request=request, current_user=user)

        assert result is user
        pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_free_plan_under_quota_passes(self) -> None:
        row = _api_usage_row(used_count=1, quota_limit=3)
        pool = _make_pool(fetchrow_return=row)
        user = _make_user(plan="free")
        request = _make_request(pool)

        result = await check_insight_quota(request=request, current_user=user)

        assert result is user

    @pytest.mark.asyncio
    async def test_free_plan_at_quota_raises_429(self) -> None:
        row = _api_usage_row(used_count=3, quota_limit=3)
        pool = _make_pool(fetchrow_return=row)
        user = _make_user(plan="free")
        request = _make_request(pool)

        with pytest.raises(HTTPException) as exc_info:
            await check_insight_quota(request=request, current_user=user)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_free_plan_over_quota_raises_429(self) -> None:
        row = _api_usage_row(used_count=5, quota_limit=3)
        pool = _make_pool(fetchrow_return=row)
        user = _make_user(plan="free")
        request = _make_request(pool)

        with pytest.raises(HTTPException) as exc_info:
            await check_insight_quota(request=request, current_user=user)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_free_plan_creates_row_on_first_access(self) -> None:
        row = _api_usage_row(used_count=0, quota_limit=3)
        pool = _make_pool(fetchrow_return=row)
        conn = pool.acquire.return_value.__aenter__.return_value
        user = _make_user(plan="free")
        request = _make_request(pool)

        await check_insight_quota(request=request, current_user=user)

        # execute (upsert) must be called
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_error_raises_500(self) -> None:
        pool = MagicMock()
        pool.acquire = MagicMock(side_effect=Exception("DB connection refused"))
        user = _make_user(plan="free")
        request = _make_request(pool)

        with pytest.raises(HTTPException) as exc_info:
            await check_insight_quota(request=request, current_user=user)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_returns_current_user_when_quota_ok(self) -> None:
        row = _api_usage_row(used_count=0, quota_limit=3)
        pool = _make_pool(fetchrow_return=row)
        user = _make_user(plan="free", user_id="user-xyz")
        request = _make_request(pool)

        result = await check_insight_quota(request=request, current_user=user)

        assert result.user_id == "user-xyz"


class TestIncrementInsightUsage:
    @pytest.mark.asyncio
    async def test_increment_usage_updates_count(self) -> None:
        pool = _make_pool()
        conn = pool.acquire.return_value.__aenter__.return_value
        reset_at = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        await increment_insight_usage(pool=pool, user_id="user-123", reset_at=reset_at)

        conn.execute.assert_awaited_once()
        sql: str = conn.execute.call_args[0][0]
        assert "UPDATE api_usage" in sql
        assert "used_count = used_count + 1" in sql

    @pytest.mark.asyncio
    async def test_increment_usage_does_not_raise_on_db_error(self) -> None:
        pool = MagicMock()
        pool.acquire = MagicMock(side_effect=Exception("DB error"))
        reset_at = datetime.now(tz=timezone.utc)

        # Must not raise — best-effort
        await increment_insight_usage(pool=pool, user_id="user-123", reset_at=reset_at)
