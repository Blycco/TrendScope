"""Tests for backend/db/queries/insights.py."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.db.queries.insights import (
    fetch_group_info,
    fetch_news_for_keyword,
    fetch_news_for_keywords,
    fetch_sns_for_keyword,
    fetch_sns_for_keywords,
    get_insight_usage,
    increment_insight_usage,
    insert_action_insight,
    upsert_insight_usage,
)


def _make_pool(
    fetch_return: object = None,
    fetchrow_return: object = None,
    fetchval_return: object = None,
) -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetchval = AsyncMock(return_value=fetchval_return)
    conn.execute = AsyncMock(return_value=None)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


def _news_rows() -> list[dict]:
    return [
        {
            "id": str(uuid.uuid4()),
            "title": "AI 트렌드 급상승",
            "url": "https://example.com/news/1",
            "source": "news_source",
            "publish_time": datetime.now(tz=timezone.utc),
            "body": "인공지능 관련 기사 본문입니다.",
        },
        {
            "id": str(uuid.uuid4()),
            "title": "AI 활용 사례",
            "url": "https://example.com/news/2",
            "source": "another_source",
            "publish_time": datetime.now(tz=timezone.utc),
            "body": "AI를 활용한 다양한 사례를 소개합니다.",
        },
    ]


def _sns_rows() -> list[dict]:
    return [
        {
            "id": str(uuid.uuid4()),
            "platform": "twitter",
            "keyword": "AI",
            "locale": "ko",
            "score": 95.5,
            "snapshot_at": datetime.now(tz=timezone.utc),
        },
        {
            "id": str(uuid.uuid4()),
            "platform": "instagram",
            "keyword": "AI 트렌드",
            "locale": "ko",
            "score": 80.0,
            "snapshot_at": datetime.now(tz=timezone.utc),
        },
    ]


def _usage_row() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "endpoint": "insights",
        "used_count": 1,
        "quota_limit": 3,
        "reset_at": datetime.now(tz=timezone.utc),
    }


class TestFetchGroupInfo:
    @pytest.mark.asyncio
    async def test_fetch_group_info_returns_record(self) -> None:
        row = {"title": "AI 트렌드", "keywords": ["AI", "인공지능"]}
        pool = _make_pool(fetchrow_return=row)

        result = await fetch_group_info(pool, str(uuid.uuid4()))

        assert result is not None
        assert result["title"] == "AI 트렌드"
        assert result["keywords"] == ["AI", "인공지능"]

    @pytest.mark.asyncio
    async def test_fetch_group_info_returns_none_for_missing(self) -> None:
        pool = _make_pool(fetchrow_return=None)

        result = await fetch_group_info(pool, str(uuid.uuid4()))

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_group_info_db_error_raises(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with pytest.raises(Exception, match="DB error"):
            await fetch_group_info(pool, str(uuid.uuid4()))


class TestFetchNewsForKeywords:
    @pytest.mark.asyncio
    async def test_fetch_news_for_keywords_returns_rows(self) -> None:
        rows = _news_rows()
        pool = _make_pool(fetch_return=rows)

        result = await fetch_news_for_keywords(pool, ["AI", "인공지능"])

        assert result == rows

    @pytest.mark.asyncio
    async def test_fetch_news_for_keywords_builds_or_query(self) -> None:
        pool = _make_pool(fetch_return=[])
        conn = pool.acquire.return_value.__aenter__.return_value

        await fetch_news_for_keywords(pool, ["AI", "트렌드"], limit=5)

        call_args = conn.fetch.call_args
        sql: str = call_args[0][0]
        assert "ILIKE $1" in sql
        assert "ILIKE $2" in sql
        assert call_args[0][1] == "%AI%"
        assert call_args[0][2] == "%트렌드%"
        assert call_args[0][3] == 5


class TestFetchSnsForKeywords:
    @pytest.mark.asyncio
    async def test_fetch_sns_for_keywords_returns_rows(self) -> None:
        rows = _sns_rows()
        pool = _make_pool(fetch_return=rows)

        result = await fetch_sns_for_keywords(pool, ["AI", "트렌드"])

        assert result == rows

    @pytest.mark.asyncio
    async def test_fetch_sns_for_keywords_builds_or_query(self) -> None:
        pool = _make_pool(fetch_return=[])
        conn = pool.acquire.return_value.__aenter__.return_value

        await fetch_sns_for_keywords(pool, ["AI", "머신러닝"], limit=10)

        call_args = conn.fetch.call_args
        sql: str = call_args[0][0]
        assert "ILIKE $1" in sql
        assert "ILIKE $2" in sql
        assert call_args[0][1] == "%AI%"
        assert call_args[0][2] == "%머신러닝%"
        assert call_args[0][3] == 10


class TestFetchNewsForKeyword:
    @pytest.mark.asyncio
    async def test_fetch_news_for_keyword(self) -> None:
        rows = _news_rows()
        pool = _make_pool(fetch_return=rows)

        result = await fetch_news_for_keyword(pool, "AI")

        assert result == rows
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_news_returns_records_with_correct_fields(self) -> None:
        rows = _news_rows()
        pool = _make_pool(fetch_return=rows)

        result = await fetch_news_for_keyword(pool, "AI")

        assert len(result) == 2
        assert result[0]["title"] == "AI 트렌드 급상승"
        assert result[0]["url"] == "https://example.com/news/1"

    @pytest.mark.asyncio
    async def test_fetch_news_uses_parameterized_query(self) -> None:
        pool = _make_pool(fetch_return=[])
        conn = pool.acquire.return_value.__aenter__.return_value

        await fetch_news_for_keyword(pool, "테스트", limit=5)

        call_args = conn.fetch.call_args
        # First positional arg is the SQL; subsequent args are parameters
        sql: str = call_args[0][0]
        assert "$1" in sql
        assert "$2" in sql
        # Keyword wrapped in % for ILIKE
        assert call_args[0][1] == "%테스트%"
        assert call_args[0][2] == 5

    @pytest.mark.asyncio
    async def test_fetch_news_db_error_raises(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=Exception("DB query failed"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with pytest.raises(Exception, match="DB query failed"):
            await fetch_news_for_keyword(pool, "AI")


class TestFetchSnsForKeyword:
    @pytest.mark.asyncio
    async def test_fetch_sns_for_keyword(self) -> None:
        rows = _sns_rows()
        pool = _make_pool(fetch_return=rows)

        result = await fetch_sns_for_keyword(pool, "AI")

        assert result == rows

    @pytest.mark.asyncio
    async def test_fetch_sns_returns_records_with_correct_fields(self) -> None:
        rows = _sns_rows()
        pool = _make_pool(fetch_return=rows)

        result = await fetch_sns_for_keyword(pool, "AI")

        assert len(result) == 2
        assert result[0]["platform"] == "twitter"
        assert result[0]["keyword"] == "AI"
        assert result[0]["score"] == 95.5

    @pytest.mark.asyncio
    async def test_fetch_sns_uses_parameterized_query(self) -> None:
        pool = _make_pool(fetch_return=[])
        conn = pool.acquire.return_value.__aenter__.return_value

        await fetch_sns_for_keyword(pool, "트렌드", limit=10)

        call_args = conn.fetch.call_args
        sql: str = call_args[0][0]
        assert "$1" in sql
        assert "$2" in sql
        assert call_args[0][1] == "%트렌드%"
        assert call_args[0][2] == 10

    @pytest.mark.asyncio
    async def test_fetch_sns_db_error_raises(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=Exception("SNS query failed"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with pytest.raises(Exception, match="SNS query failed"):
            await fetch_sns_for_keyword(pool, "AI")


class TestInsertActionInsight:
    @pytest.mark.asyncio
    async def test_insert_action_insight_returns_id(self) -> None:
        expected_id = str(uuid.uuid4())
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": expected_id})
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        result = await insert_action_insight(
            pool=pool,
            trend_kw="AI 트렌드",
            role="marketer",
            locale="ko",
            content={"ad_opportunities": ["기회 1"], "source_urls": []},
        )

        assert result == expected_id

    @pytest.mark.asyncio
    async def test_insert_action_insight_uses_parameterized_query(self) -> None:
        expected_id = str(uuid.uuid4())
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": expected_id})
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        await insert_action_insight(
            pool=pool,
            trend_kw="테스트",
            role="creator",
            locale="en",
            content={"title_drafts": [], "source_urls": []},
        )

        call_args = conn.fetchrow.call_args
        sql: str = call_args[0][0]
        assert "INSERT INTO action_insight" in sql
        assert "$1" in sql
        assert "$2" in sql

    @pytest.mark.asyncio
    async def test_insert_action_insight_db_error_raises(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=Exception("Insert failed"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with pytest.raises(Exception, match="Insert failed"):
            await insert_action_insight(
                pool=pool,
                trend_kw="AI",
                role="marketer",
                locale="ko",
                content={},
            )


class TestGetInsightUsage:
    @pytest.mark.asyncio
    async def test_get_insight_usage_returns_record(self) -> None:
        row = _usage_row()
        pool = _make_pool(fetchrow_return=row)
        reset_at = datetime.now(tz=timezone.utc)

        result = await get_insight_usage(
            pool=pool, user_id="user-123", endpoint="insights", reset_at=reset_at
        )

        assert result == row
        assert result["used_count"] == 1
        assert result["quota_limit"] == 3

    @pytest.mark.asyncio
    async def test_get_insight_usage_returns_none(self) -> None:
        pool = _make_pool(fetchrow_return=None)
        reset_at = datetime.now(tz=timezone.utc)

        result = await get_insight_usage(
            pool=pool, user_id="user-456", endpoint="insights", reset_at=reset_at
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_insight_usage_db_error_raises(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        reset_at = datetime.now(tz=timezone.utc)

        with pytest.raises(Exception, match="DB error"):
            await get_insight_usage(
                pool=pool, user_id="user-123", endpoint="insights", reset_at=reset_at
            )


class TestUpsertInsightUsage:
    @pytest.mark.asyncio
    async def test_upsert_insight_usage_executes(self) -> None:
        pool = _make_pool()
        conn = pool.acquire.return_value.__aenter__.return_value
        reset_at = datetime.now(tz=timezone.utc)

        await upsert_insight_usage(
            pool=pool,
            user_id="user-123",
            endpoint="insights",
            quota_limit=3,
            reset_at=reset_at,
        )

        conn.execute.assert_awaited_once()
        sql: str = conn.execute.call_args[0][0]
        assert "INSERT INTO api_usage" in sql
        assert "ON CONFLICT" in sql

    @pytest.mark.asyncio
    async def test_upsert_insight_usage_db_error_raises(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("Upsert failed"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        reset_at = datetime.now(tz=timezone.utc)

        with pytest.raises(Exception, match="Upsert failed"):
            await upsert_insight_usage(
                pool=pool,
                user_id="user-123",
                endpoint="insights",
                quota_limit=3,
                reset_at=reset_at,
            )


class TestIncrementInsightUsage:
    @pytest.mark.asyncio
    async def test_increment_insight_usage_executes(self) -> None:
        pool = _make_pool()
        conn = pool.acquire.return_value.__aenter__.return_value
        reset_at = datetime.now(tz=timezone.utc)

        await increment_insight_usage(
            pool=pool, user_id="user-123", endpoint="insights", reset_at=reset_at
        )

        conn.execute.assert_awaited_once()
        sql: str = conn.execute.call_args[0][0]
        assert "UPDATE api_usage" in sql
        assert "used_count = used_count + 1" in sql

    @pytest.mark.asyncio
    async def test_increment_insight_usage_db_error_raises(self) -> None:
        pool = MagicMock()
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("Update failed"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        reset_at = datetime.now(tz=timezone.utc)

        with pytest.raises(Exception, match="Update failed"):
            await increment_insight_usage(
                pool=pool, user_id="user-123", endpoint="insights", reset_at=reset_at
            )
