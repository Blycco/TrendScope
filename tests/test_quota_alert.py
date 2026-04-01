"""Tests for backend/common/quota_alert.py — rate limit detection and alert recording."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from backend.common.quota_alert import (
    handle_api_exception,
    is_rate_limit_error,
    record_quota_alert,
)

# ---------------------------------------------------------------------------
# is_rate_limit_error
# ---------------------------------------------------------------------------


class TestIsRateLimitError:
    def test_httpx_429(self) -> None:
        request = httpx.Request("GET", "https://api.example.com/test")
        response = httpx.Response(429, request=request)
        exc = httpx.HTTPStatusError("rate limited", request=request, response=response)

        is_rl, code, detail = is_rate_limit_error(exc)
        assert is_rl is True
        assert code == 429
        assert detail is not None

    def test_httpx_500_not_rate_limit(self) -> None:
        request = httpx.Request("GET", "https://api.example.com/test")
        response = httpx.Response(500, request=request)
        exc = httpx.HTTPStatusError("server error", request=request, response=response)

        is_rl, code, detail = is_rate_limit_error(exc)
        assert is_rl is False
        assert code is None

    def test_generic_exception_not_rate_limit(self) -> None:
        exc = RuntimeError("some error")
        is_rl, code, detail = is_rate_limit_error(exc)
        assert is_rl is False
        assert code is None
        assert detail is None

    def test_openai_rate_limit(self) -> None:
        try:
            from openai import RateLimitError

            exc = RateLimitError(
                message="Rate limit reached",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
            is_rl, code, detail = is_rate_limit_error(exc)
            assert is_rl is True
            assert code == 429
        except ImportError:
            pytest.skip("openai not installed")

    def test_gemini_resource_exhausted(self) -> None:
        try:
            from google.api_core.exceptions import ResourceExhausted

            exc = ResourceExhausted("Quota exceeded")
            is_rl, code, detail = is_rate_limit_error(exc)
            assert is_rl is True
            assert code == 429
        except ImportError:
            pytest.skip("google-api-core not installed")


# ---------------------------------------------------------------------------
# record_quota_alert
# ---------------------------------------------------------------------------


class TestRecordQuotaAlert:
    @pytest.mark.asyncio
    async def test_inserts_alert(self) -> None:
        conn = AsyncMock()
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)

        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch("backend.common.quota_alert._send_and_mark_email", new_callable=AsyncMock):
            await record_quota_alert(
                pool,
                service_name="youtube",
                error_type="rate_limit_429",
                status_code=429,
                detail="Too Many Requests",
                endpoint_url="https://www.googleapis.com/youtube/v3/videos",
            )

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "INSERT INTO api_quota_alert" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_debounce_skips_email(self) -> None:
        conn = AsyncMock()
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=5)

        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch("backend.common.quota_alert.asyncio") as mock_asyncio:
            await record_quota_alert(pool, service_name="youtube")
            mock_asyncio.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_alert_queues_email(self) -> None:
        conn = AsyncMock()
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)

        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch("backend.common.quota_alert.asyncio") as mock_asyncio:
            await record_quota_alert(pool, service_name="youtube")
            mock_asyncio.create_task.assert_called_once()


# ---------------------------------------------------------------------------
# handle_api_exception
# ---------------------------------------------------------------------------


class TestHandleApiException:
    @pytest.mark.asyncio
    async def test_429_triggers_record(self) -> None:
        request = httpx.Request("GET", "https://api.example.com/test")
        response = httpx.Response(429, request=request)
        exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
        pool = MagicMock()

        with patch(
            "backend.common.quota_alert.record_quota_alert",
            new_callable=AsyncMock,
        ) as mock_record:
            await handle_api_exception(exc, "youtube", pool)
            mock_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_429_does_not_record(self) -> None:
        exc = RuntimeError("some error")
        pool = MagicMock()

        with patch(
            "backend.common.quota_alert.record_quota_alert",
            new_callable=AsyncMock,
        ) as mock_record:
            await handle_api_exception(exc, "youtube", pool)
            mock_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_pool_does_nothing(self) -> None:
        request = httpx.Request("GET", "https://api.example.com/test")
        response = httpx.Response(429, request=request)
        exc = httpx.HTTPStatusError("rate limited", request=request, response=response)

        with patch(
            "backend.common.quota_alert.record_quota_alert",
            new_callable=AsyncMock,
        ) as mock_record:
            await handle_api_exception(exc, "youtube", None)
            mock_record.assert_not_called()
