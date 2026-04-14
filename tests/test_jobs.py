"""Unit tests for scheduled jobs: plan_expiry and quota_reset."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


class TestPlanExpiryJob:
    async def test_no_expired_subscriptions(self, mock_pool: MagicMock) -> None:
        from backend.jobs.plan_expiry import run_plan_expiry

        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[])

        count = await run_plan_expiry(mock_pool)
        assert count == 0

    async def test_expires_subscriptions_and_downgrades_plan(self, mock_pool: MagicMock) -> None:
        from backend.jobs.plan_expiry import run_plan_expiry

        row1 = MagicMock()
        row1.__getitem__ = lambda self, key: {
            "id": "sub-id-1",
            "user_id": "user-id-1",
        }[key]
        row2 = MagicMock()
        row2.__getitem__ = lambda self, key: {
            "id": "sub-id-2",
            "user_id": "user-id-2",
        }[key]

        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[row1, row2])
        conn.executemany = AsyncMock()

        count = await run_plan_expiry(mock_pool)
        assert count == 2
        conn.executemany.assert_called_once()

    async def test_deduplicates_user_ids(self, mock_pool: MagicMock) -> None:
        """Same user with two expired subscriptions — executemany only runs once per user."""
        from backend.jobs.plan_expiry import run_plan_expiry

        same_user_id = "user-id-dup"

        def make_row(sub_id: str) -> MagicMock:
            row = MagicMock()
            row.__getitem__ = lambda self, key: {
                "id": sub_id,
                "user_id": same_user_id,
            }[key]
            return row

        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(return_value=[make_row("sub-1"), make_row("sub-2")])
        conn.executemany = AsyncMock()

        count = await run_plan_expiry(mock_pool)
        assert count == 2
        # unique user_ids deduplicated — should be 1 entry
        args = conn.executemany.call_args[0]
        assert len(args[1]) == 1

    async def test_raises_on_db_error(self, mock_pool: MagicMock) -> None:
        from backend.jobs.plan_expiry import run_plan_expiry

        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.fetch = AsyncMock(side_effect=RuntimeError("db error"))

        with pytest.raises(RuntimeError, match="db error"):
            await run_plan_expiry(mock_pool)


class TestQuotaResetJob:
    async def test_resets_rows(self, mock_pool: MagicMock) -> None:
        from backend.jobs.quota_reset import run_quota_reset

        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock(return_value="UPDATE 5")

        count = await run_quota_reset(mock_pool)
        assert count == 5

    async def test_no_rows_to_reset(self, mock_pool: MagicMock) -> None:
        from backend.jobs.quota_reset import run_quota_reset

        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock(return_value="UPDATE 0")

        count = await run_quota_reset(mock_pool)
        assert count == 0

    async def test_raises_on_db_error(self, mock_pool: MagicMock) -> None:
        from backend.jobs.quota_reset import run_quota_reset

        conn = mock_pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock(side_effect=RuntimeError("quota reset error"))

        with pytest.raises(RuntimeError, match="quota reset error"):
            await run_quota_reset(mock_pool)


class TestSchedulerJobRegistration:
    def test_all_required_jobs_registered(self, mock_pool: MagicMock) -> None:
        from backend.crawler.scheduler import create_scheduler

        scheduler = create_scheduler(mock_pool)
        registered = {job.id for job in scheduler.get_jobs()}
        required = {
            "news_crawl",
            "sns_collect",
            "community_crawl",
            "early_trend_update",
            "naver_datalab",
            "keyword_snapshot",
            "quota_reset",
            "daily_digest",
            "keyword_review",
            "brand_alert",
            "plan_expiry",
        }
        missing = required - registered
        assert not missing, f"scheduler missing jobs: {missing}"
