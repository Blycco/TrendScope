"""Tests for backend.crawler.sources.naver_datalab_crawler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _make_db_pool(
    *,
    quota_active: bool = True,
    quota_limit: int = 1000,
    quota_used: int = 0,
    news_group_rows: list | None = None,
) -> MagicMock:
    """Helper: build a mock asyncpg Pool."""
    pool = MagicMock()

    # fetchrow for check_quota
    quota_row = {
        "is_active": quota_active,
        "quota_limit": quota_limit,
        "quota_used": quota_used,
    }
    pool.fetchrow = AsyncMock(return_value=quota_row)

    # execute for increment_quota
    pool.execute = AsyncMock(return_value="UPDATE 1")

    # conn used inside acquire() context manager
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    rows = news_group_rows if news_group_rows is not None else []
    conn.fetch = AsyncMock(return_value=rows)

    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


def _make_datalab_response(titles: list[str] | None = None) -> dict:
    """Build a fake DataLab API response."""
    if titles is None:
        titles = ["AI·기술", "경제·금융"]
    results = []
    for title in titles:
        results.append(
            {
                "title": title,
                "keywords": [title],
                "data": [
                    {"period": "2026-04-01", "ratio": 80.0},
                    {"period": "2026-04-02", "ratio": 85.0},
                    {"period": "2026-04-03", "ratio": 90.0},
                ],
            }
        )
    return {"results": results}


class TestFetchNaverTrends:
    @pytest.mark.asyncio
    async def test_normal_response_returns_results(self) -> None:
        """fetch_naver_trends: 정상 응답 시 results 리스트 반환."""
        from backend.crawler.sources.naver_datalab_crawler import fetch_naver_trends

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=_make_datalab_response(["AI·기술"]))

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        naver_env = {"NAVER_CLIENT_ID": "cid", "NAVER_CLIENT_SECRET": "csec"}
        with patch("httpx.AsyncClient", return_value=mock_cm):
            with patch.dict("os.environ", naver_env):
                results = await fetch_naver_trends([{"groupName": "AI·기술", "keywords": ["AI"]}])

        assert len(results) == 1
        assert results[0]["title"] == "AI·기술"

    @pytest.mark.asyncio
    async def test_api_error_returns_empty_list(self) -> None:
        """fetch_naver_trends: API 에러(401) 시 빈 리스트 반환 (예외 전파 없음)."""
        from backend.crawler.sources.naver_datalab_crawler import fetch_naver_trends

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=MagicMock(status_code=401),
            )
        )

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        naver_env = {"NAVER_CLIENT_ID": "cid", "NAVER_CLIENT_SECRET": "csec"}
        with patch("httpx.AsyncClient", return_value=mock_cm):
            with patch.dict("os.environ", naver_env):
                results = await fetch_naver_trends([{"groupName": "test", "keywords": ["test"]}])

        assert results == []

    @pytest.mark.asyncio
    async def test_missing_env_vars_returns_empty_list(self) -> None:
        """fetch_naver_trends: 환경변수 미설정 시 빈 리스트 반환."""
        import os

        from backend.crawler.sources.naver_datalab_crawler import fetch_naver_trends

        with patch.dict("os.environ", {}, clear=True):
            os.environ.pop("NAVER_CLIENT_ID", None)
            os.environ.pop("NAVER_CLIENT_SECRET", None)
            results = await fetch_naver_trends([{"groupName": "test", "keywords": ["test"]}])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_processing_5_plus_1(self) -> None:
        """fetch_naver_trends: keyword_groups 6개 → 2번 API 호출 (5+1 배치)."""
        from backend.crawler.sources.naver_datalab_crawler import fetch_naver_trends

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"results": []})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        groups = [{"groupName": f"group{i}", "keywords": [f"kw{i}"]} for i in range(6)]

        naver_env = {"NAVER_CLIENT_ID": "cid", "NAVER_CLIENT_SECRET": "csec"}
        with patch("httpx.AsyncClient", return_value=mock_cm):
            with patch.dict("os.environ", naver_env):
                await fetch_naver_trends(groups)

        assert mock_client.post.call_count == 2


class TestCrawlNaverDatalab:
    @pytest.mark.asyncio
    async def test_quota_exceeded_returns_empty_list(self) -> None:
        """crawl_naver_datalab: quota 초과 시 빈 리스트 반환, API 미호출."""
        from backend.crawler.sources.naver_datalab_crawler import crawl_naver_datalab

        pool = _make_db_pool(quota_used=1000, quota_limit=1000)

        with patch(
            "backend.crawler.sources.naver_datalab_crawler.fetch_naver_trends"
        ) as mock_fetch:
            result = await crawl_naver_datalab(pool)

        assert result == []
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_flow_inserts_sns_trend(self) -> None:
        """crawl_naver_datalab: 정상 흐름 시 sns_trend INSERT 실행."""
        from backend.crawler.sources.naver_datalab_crawler import crawl_naver_datalab

        pool = _make_db_pool(quota_used=0, quota_limit=1000)

        fake_results = [
            {
                "title": "AI·기술",
                "keywords": ["인공지능", "AI"],
                "data": [
                    {"period": "2026-04-01", "ratio": 80.0},
                    {"period": "2026-04-02", "ratio": 90.0},
                ],
            }
        ]

        with patch(
            "backend.crawler.sources.naver_datalab_crawler.fetch_naver_trends",
            new_callable=AsyncMock,
            return_value=fake_results,
        ):
            saved = await crawl_naver_datalab(pool)

        assert len(saved) == 1
        assert saved[0]["keyword"] == "AI·기술"
        assert isinstance(saved[0]["score"], float)

        # Verify INSERT was called on the connection
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_called_once()
        call_sql: str = conn.execute.call_args[0][0]
        assert "INSERT INTO sns_trend" in call_sql


class TestBuildKeywordGroups:
    @pytest.mark.asyncio
    async def test_no_db_keywords_returns_defaults(self) -> None:
        """_build_keyword_groups: DB 키워드 없을 때 _DEFAULT_KEYWORD_GROUPS 반환."""
        from backend.crawler.sources.naver_datalab_crawler import (
            _DEFAULT_KEYWORD_GROUPS,
            _build_keyword_groups,
        )

        pool = _make_db_pool(news_group_rows=[])
        result = await _build_keyword_groups(pool)
        assert result == _DEFAULT_KEYWORD_GROUPS

    @pytest.mark.asyncio
    async def test_db_keywords_build_groups(self) -> None:
        """_build_keyword_groups: DB에서 키워드 로드 시 그룹 동적 생성."""
        from backend.crawler.sources.naver_datalab_crawler import _build_keyword_groups

        rows = [{"kw": f"keyword{i}"} for i in range(6)]
        pool = _make_db_pool(news_group_rows=rows)
        result = await _build_keyword_groups(pool)

        # 6 keywords → 2 groups (5 + 1)
        assert len(result) == 2
        assert result[0]["keywords"][0] == "keyword0"
        assert len(result[0]["keywords"]) == 5
        assert len(result[1]["keywords"]) == 1
