"""Tests for feed_source DB query layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def _mock_pool(
    *,
    fetch_result: list | None = None,
    fetchrow_result: object = None,
    fetchval_result: object = None,
    execute_result: str = "UPDATE 1",
) -> MagicMock:
    """Create a mock asyncpg pool with preset return values."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_result or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.fetchval = AsyncMock(return_value=fetchval_result)
    conn.execute = AsyncMock(return_value=execute_result)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool, conn


class TestListFeedSources:
    async def test_list_no_filters(self) -> None:
        from backend.db.queries.feed_sources import list_feed_sources

        pool, conn = _mock_pool(fetchval_result=5, fetch_result=[])
        rows, total = await list_feed_sources(pool)
        assert total == 5
        assert conn.fetchval.await_count == 1
        assert conn.fetch.await_count == 1

    async def test_list_with_source_type_filter(self) -> None:
        from backend.db.queries.feed_sources import list_feed_sources

        pool, conn = _mock_pool(fetchval_result=3, fetch_result=[])
        rows, total = await list_feed_sources(pool, source_type="rss")
        assert total == 3
        call_args = conn.fetchval.call_args
        assert "rss" in call_args.args

    async def test_list_with_search(self) -> None:
        from backend.db.queries.feed_sources import list_feed_sources

        pool, conn = _mock_pool(fetchval_result=1, fetch_result=[])
        rows, total = await list_feed_sources(pool, search="naver")
        assert total == 1
        call_args = conn.fetchval.call_args
        assert "%naver%" in call_args.args

    async def test_list_with_health_status(self) -> None:
        from backend.db.queries.feed_sources import list_feed_sources

        pool, conn = _mock_pool(fetchval_result=2, fetch_result=[])
        rows, total = await list_feed_sources(pool, health_status="error")
        assert total == 2
        call_args = conn.fetchval.call_args
        assert "error" in call_args.args

    async def test_list_pagination(self) -> None:
        from backend.db.queries.feed_sources import list_feed_sources

        pool, conn = _mock_pool(fetchval_result=100, fetch_result=[])
        rows, total = await list_feed_sources(pool, page=3, page_size=20)
        assert total == 100
        # offset should be (3-1)*20 = 40
        fetch_args = conn.fetch.call_args.args
        assert 20 in fetch_args
        assert 40 in fetch_args


class TestGetFeedSource:
    async def test_get_existing(self) -> None:
        from backend.db.queries.feed_sources import get_feed_source

        row = MagicMock()
        pool, conn = _mock_pool(fetchrow_result=row)
        result = await get_feed_source(pool, "some-uuid")
        assert result is row

    async def test_get_not_found(self) -> None:
        from backend.db.queries.feed_sources import get_feed_source

        pool, conn = _mock_pool(fetchrow_result=None)
        result = await get_feed_source(pool, "nonexistent")
        assert result is None


class TestCreateFeedSource:
    async def test_create_success(self) -> None:
        from backend.db.queries.feed_sources import create_feed_source

        row = MagicMock()
        pool, conn = _mock_pool(fetchrow_result=row)
        result = await create_feed_source(
            pool,
            name="Test Feed",
            url="https://example.com/rss",
            source_type="rss",
            category="general",
            locale="ko",
        )
        assert result is row
        call_args = conn.fetchrow.call_args.args
        assert "https://example.com/rss" in call_args

    async def test_create_with_source_config_id(self) -> None:
        from backend.db.queries.feed_sources import create_feed_source

        row = MagicMock()
        pool, conn = _mock_pool(fetchrow_result=row)
        result = await create_feed_source(
            pool,
            name="Test",
            url="https://example.com/feed",
            source_type="rss",
            source_config_id="some-uuid",
        )
        assert result is row


class TestUpdateFeedSource:
    async def test_update_name(self) -> None:
        from backend.db.queries.feed_sources import update_feed_source

        row = MagicMock()
        pool, conn = _mock_pool(fetchrow_result=row)
        result = await update_feed_source(pool, "feed-id", name="New Name")
        assert result is row
        query = conn.fetchrow.call_args.args[0]
        assert "name = $2" in query

    async def test_update_no_fields_returns_none(self) -> None:
        from backend.db.queries.feed_sources import update_feed_source

        pool, conn = _mock_pool()
        result = await update_feed_source(pool, "feed-id")
        assert result is None

    async def test_update_ignores_unknown_columns(self) -> None:
        from backend.db.queries.feed_sources import update_feed_source

        pool, conn = _mock_pool(fetchrow_result=None)
        result = await update_feed_source(pool, "feed-id", hacker_field="drop table")
        assert result is None
        conn.fetchrow.assert_not_awaited()

    async def test_update_config_uses_jsonb_cast(self) -> None:
        from backend.db.queries.feed_sources import update_feed_source

        row = MagicMock()
        pool, conn = _mock_pool(fetchrow_result=row)
        result = await update_feed_source(pool, "feed-id", config='{"key": "val"}')
        assert result is row
        query = conn.fetchrow.call_args.args[0]
        assert "config = $2::jsonb" in query


class TestDeleteFeedSource:
    async def test_delete_success(self) -> None:
        from backend.db.queries.feed_sources import delete_feed_source

        pool, conn = _mock_pool(execute_result="DELETE 1")
        assert await delete_feed_source(pool, "feed-id") is True

    async def test_delete_not_found(self) -> None:
        from backend.db.queries.feed_sources import delete_feed_source

        pool, conn = _mock_pool(execute_result="DELETE 0")
        assert await delete_feed_source(pool, "feed-id") is False


class TestBulkToggle:
    async def test_bulk_enable(self) -> None:
        from backend.db.queries.feed_sources import bulk_toggle_feed_sources

        pool, conn = _mock_pool(execute_result="UPDATE 3")
        count = await bulk_toggle_feed_sources(pool, ["a", "b", "c"], is_active=True)
        assert count == 3
        call_args = conn.execute.call_args.args
        assert True in call_args
        assert ["a", "b", "c"] in call_args


class TestGetFeedSourcesForCrawl:
    async def test_returns_active_feeds(self) -> None:
        from backend.db.queries.feed_sources import get_feed_sources_for_crawl

        rows = [MagicMock(), MagicMock()]
        pool, conn = _mock_pool(fetch_result=rows)
        result = await get_feed_sources_for_crawl(pool, "rss")
        assert len(result) == 2
        call_args = conn.fetch.call_args.args
        assert "rss" in call_args


class TestUpdateFeedHealth:
    async def test_success_resets_failures(self) -> None:
        from backend.db.queries.feed_sources import update_feed_health

        pool, conn = _mock_pool()
        await update_feed_health(pool, "feed-id", success=True, latency_ms=150.0)
        query = conn.execute.call_args.args[0]
        assert "consecutive_failures = 0" in query
        assert "last_success_at = now()" in query

    async def test_failure_increments_failures(self) -> None:
        from backend.db.queries.feed_sources import update_feed_health

        pool, conn = _mock_pool()
        await update_feed_health(pool, "feed-id", success=False, latency_ms=5000.0, error="timeout")
        query = conn.execute.call_args.args[0]
        assert "consecutive_failures = consecutive_failures + 1" in query
        assert "last_error = $2" in query
        assert "total_error_count = total_error_count + 1" in query

    async def test_latency_ema_calculation(self) -> None:
        from backend.db.queries.feed_sources import update_feed_health

        pool, conn = _mock_pool()
        await update_feed_health(pool, "feed-id", success=True, latency_ms=200.0)
        query = conn.execute.call_args.args[0]
        assert "avg_latency_ms * 0.7" in query


class TestGetFeedHealthSummary:
    async def test_returns_aggregated(self) -> None:
        from backend.db.queries.feed_sources import get_feed_health_summary

        rows = [MagicMock()]
        pool, conn = _mock_pool(fetch_result=rows)
        result = await get_feed_health_summary(pool)
        assert len(result) == 1
        query = conn.fetch.call_args.args[0]
        assert "GROUP BY source_type" in query
        assert "FILTER" in query
