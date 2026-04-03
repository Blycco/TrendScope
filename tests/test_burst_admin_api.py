"""Tests for admin burst jobs API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.api.schemas.admin import BurstTriggerRequest


class TestBurstTriggerRequestSchema:
    def test_valid_request(self) -> None:
        req = BurstTriggerRequest(keywords=["AI", "트렌드"])
        assert req.locale == "ko"
        assert len(req.keywords) == 2

    def test_invalid_locale(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BurstTriggerRequest(keywords=["AI"], locale="invalid")

    def test_empty_keywords_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BurstTriggerRequest(keywords=[])


class TestListBurstJobs:
    @pytest.mark.asyncio
    async def test_list_returns_paginated(self) -> None:
        """Verify the endpoint queries burst_job_log with pagination."""
        from backend.api.routers.admin.burst_jobs import list_burst_jobs

        mock_request = MagicMock()
        mock_pool = MagicMock()
        mock_pool.fetchval = AsyncMock(return_value=0)
        mock_pool.fetch = AsyncMock(return_value=[])
        mock_request.app.state.db_pool = mock_pool

        mock_user = MagicMock()

        result = await list_burst_jobs(
            request=mock_request,
            status=None,
            trigger_source=None,
            page=1,
            page_size=50,
            current_user=mock_user,
        )

        assert result.total == 0
        assert result.items == []
        assert result.page == 1

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self) -> None:
        from backend.api.routers.admin.burst_jobs import list_burst_jobs

        mock_request = MagicMock()
        mock_pool = MagicMock()
        mock_pool.fetchval = AsyncMock(return_value=0)
        mock_pool.fetch = AsyncMock(return_value=[])
        mock_request.app.state.db_pool = mock_pool

        mock_user = MagicMock()

        result = await list_burst_jobs(
            request=mock_request,
            status="success",
            trigger_source=None,
            page=1,
            page_size=20,
            current_user=mock_user,
        )

        assert result.total == 0
        call_args = mock_pool.fetchval.call_args
        assert "status = $1" in call_args[0][0]


class TestTriggerBurstJob:
    @pytest.mark.asyncio
    async def test_triggers_and_returns_result(self) -> None:
        from backend.api.routers.admin.burst_jobs import trigger_burst_job

        mock_request = MagicMock()
        mock_pool = MagicMock()
        mock_request.app.state.db_pool = mock_pool
        mock_user = MagicMock()
        body = BurstTriggerRequest(keywords=["AI", "트렌드"])

        with patch(
            "backend.api.routers.admin.burst_jobs.manual_burst_trigger",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "articles_found": 5,
                "duration_ms": 1200.0,
                "log_id": 1,
            },
        ):
            result = await trigger_burst_job(
                body=body,
                request=mock_request,
                current_user=mock_user,
            )

        assert result["success"] is True
        assert result["articles_found"] == 5

    @pytest.mark.asyncio
    async def test_rate_limited_returns_429(self) -> None:
        from backend.api.routers.admin.burst_jobs import trigger_burst_job
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_pool = MagicMock()
        mock_request.app.state.db_pool = mock_pool
        mock_user = MagicMock()
        body = BurstTriggerRequest(keywords=["AI"])

        with (
            patch(
                "backend.api.routers.admin.burst_jobs.manual_burst_trigger",
                new_callable=AsyncMock,
                return_value={"success": False, "error": "rate_limited"},
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await trigger_burst_job(
                body=body,
                request=mock_request,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 429
