"""Tests for backend.jobs.burst_job."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.jobs.burst_job import (
    find_burst_candidates,
    manual_burst_trigger,
    run_burst_job,
)


def _make_pool(
    fetch_result: list | None = None,
    fetchval_result: object = None,
) -> MagicMock:
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=fetch_result or [])
    pool.fetchval = AsyncMock(return_value=fetchval_result)
    pool.execute = AsyncMock()
    return pool


def _make_candidate(
    score: float = 0.85,
    keywords: list[str] | None = None,
    locale: str = "ko",
) -> MagicMock:
    row = MagicMock()
    data = {
        "id": uuid.uuid4(),
        "keywords": keywords or ["AI", "트렌드", "기술"],
        "locale": locale,
        "early_trend_score": score,
    }
    row.__getitem__ = lambda self, key: data[key]
    return row


class TestFindBurstCandidates:
    @pytest.mark.asyncio
    async def test_returns_groups_above_threshold(self) -> None:
        candidates = [_make_candidate(score=0.85)]
        pool = _make_pool(fetch_result=candidates)
        result = await find_burst_candidates(pool, threshold=0.75, cooldown_hours=2)
        assert len(result) == 1
        pool.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_candidates(self) -> None:
        pool = _make_pool(fetch_result=[])
        result = await find_burst_candidates(pool, threshold=0.75, cooldown_hours=2)
        assert result == []

    @pytest.mark.asyncio
    async def test_handles_db_error(self) -> None:
        pool = MagicMock()
        pool.fetch = AsyncMock(side_effect=RuntimeError("db down"))
        result = await find_burst_candidates(pool, threshold=0.75, cooldown_hours=2)
        assert result == []


class TestRunBurstJob:
    @pytest.mark.asyncio
    async def test_skips_when_lock_held(self) -> None:
        pool = _make_pool()
        with patch(
            "backend.jobs.burst_job._acquire_burst_lock",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await run_burst_job(pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_candidates(self) -> None:
        pool = _make_pool()
        with (
            patch(
                "backend.jobs.burst_job._acquire_burst_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.jobs.burst_job._release_burst_lock",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.jobs.burst_job.get_burst_threshold",
                new_callable=AsyncMock,
                return_value=0.75,
            ),
            patch(
                "backend.jobs.burst_job.get_burst_cooldown",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch(
                "backend.jobs.burst_job.find_burst_candidates",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await run_burst_job(pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_triggers_crawl_for_candidates(self) -> None:
        pool = _make_pool(fetchval_result=1)
        candidate = _make_candidate(score=0.85)

        with (
            patch(
                "backend.jobs.burst_job._acquire_burst_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.jobs.burst_job._release_burst_lock",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.jobs.burst_job.get_burst_threshold",
                new_callable=AsyncMock,
                return_value=0.75,
            ),
            patch(
                "backend.jobs.burst_job.get_burst_cooldown",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch(
                "backend.jobs.burst_job.find_burst_candidates",
                new_callable=AsyncMock,
                return_value=[candidate],
            ),
            patch(
                "backend.jobs.burst_job.run_burst_crawl",
                new_callable=AsyncMock,
                return_value=5,
            ) as mock_crawl,
        ):
            result = await run_burst_job(pool)

        assert result == 1
        mock_crawl.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_crawl_error(self) -> None:
        pool = _make_pool(fetchval_result=1)
        candidate = _make_candidate(score=0.85)

        with (
            patch(
                "backend.jobs.burst_job._acquire_burst_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.jobs.burst_job._release_burst_lock",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.jobs.burst_job.get_burst_threshold",
                new_callable=AsyncMock,
                return_value=0.75,
            ),
            patch(
                "backend.jobs.burst_job.get_burst_cooldown",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch(
                "backend.jobs.burst_job.find_burst_candidates",
                new_callable=AsyncMock,
                return_value=[candidate],
            ),
            patch(
                "backend.jobs.burst_job.run_burst_crawl",
                new_callable=AsyncMock,
                side_effect=RuntimeError("crawl failed"),
            ),
        ):
            result = await run_burst_job(pool)

        assert result == 0


class TestManualBurstTrigger:
    @pytest.mark.asyncio
    async def test_triggers_with_keywords(self) -> None:
        pool = _make_pool(fetchval_result=1)

        with (
            patch(
                "backend.jobs.burst_job._acquire_burst_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.jobs.burst_job._release_burst_lock",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.jobs.burst_job.run_burst_crawl",
                new_callable=AsyncMock,
                return_value=3,
            ),
        ):
            result = await manual_burst_trigger(pool, keywords=["AI", "트렌드"])

        assert result["success"] is True
        assert result["articles_found"] == 3
        assert result["log_id"] == 1

    @pytest.mark.asyncio
    async def test_rate_limited(self) -> None:
        pool = _make_pool()

        with patch(
            "backend.jobs.burst_job._acquire_burst_lock",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await manual_burst_trigger(pool, keywords=["AI"])

        assert result["success"] is False
        assert result["error"] == "rate_limited"
