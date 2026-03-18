"""Tests for backend/api/middleware/rate_limit.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.api.middleware.rate_limit import rate_limit_check
from backend.auth.dependencies import CurrentUser
from fastapi import HTTPException


def _make_user(user_id: str = "user-123", plan: str = "free") -> CurrentUser:
    return CurrentUser(user_id=user_id, plan=plan, role="general")


def _make_request() -> MagicMock:
    request = MagicMock()
    request.app = MagicMock()
    request.app.state = MagicMock()
    return request


class TestRateLimitCheck:
    @pytest.mark.asyncio
    async def test_under_limit_passes(self) -> None:
        user = _make_user()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        request = _make_request()

        with patch(
            "backend.api.middleware.rate_limit.get_redis",
            return_value=mock_redis,
        ):
            result = await rate_limit_check(request=request, current_user=user)

        assert result is user

    @pytest.mark.asyncio
    async def test_at_limit_passes(self) -> None:
        user = _make_user()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=300)
        mock_redis.expire = AsyncMock()
        request = _make_request()

        with patch(
            "backend.api.middleware.rate_limit.get_redis",
            return_value=mock_redis,
        ):
            result = await rate_limit_check(request=request, current_user=user)

        assert result is user

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self) -> None:
        user = _make_user()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=301)
        mock_redis.expire = AsyncMock()
        request = _make_request()

        with patch(
            "backend.api.middleware.rate_limit.get_redis",
            return_value=mock_redis,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await rate_limit_check(request=request, current_user=user)

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["code"] == "E0041"

    @pytest.mark.asyncio
    async def test_redis_error_fail_open(self) -> None:
        user = _make_user()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(side_effect=Exception("Redis connection refused"))
        request = _make_request()

        with patch(
            "backend.api.middleware.rate_limit.get_redis",
            return_value=mock_redis,
        ):
            result = await rate_limit_check(request=request, current_user=user)

        # Fail-open: user is returned even when Redis is down
        assert result is user

    @pytest.mark.asyncio
    async def test_expire_called_on_first_request(self) -> None:
        user = _make_user()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        request = _make_request()

        with patch(
            "backend.api.middleware.rate_limit.get_redis",
            return_value=mock_redis,
        ):
            await rate_limit_check(request=request, current_user=user)

        mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expire_not_called_on_subsequent_requests(self) -> None:
        user = _make_user()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=5)
        mock_redis.expire = AsyncMock()
        request = _make_request()

        with patch(
            "backend.api.middleware.rate_limit.get_redis",
            return_value=mock_redis,
        ):
            await rate_limit_check(request=request, current_user=user)

        mock_redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_current_user_on_success(self) -> None:
        user = _make_user(user_id="abc-999", plan="pro")
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=50)
        mock_redis.expire = AsyncMock()
        request = _make_request()

        with patch(
            "backend.api.middleware.rate_limit.get_redis",
            return_value=mock_redis,
        ):
            result = await rate_limit_check(request=request, current_user=user)

        assert result.user_id == "abc-999"
        assert result.plan == "pro"
