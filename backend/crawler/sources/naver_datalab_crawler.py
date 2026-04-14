"""Naver DataLab 검색어트렌드 크롤러. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

import asyncpg
import httpx
import structlog

from backend.common.metrics import CRAWLER_REQUESTS
from backend.crawler.quota_guard import check_quota, increment_quota

logger = structlog.get_logger(__name__)

_DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
_HTTP_TIMEOUT = 10.0

_DEFAULT_KEYWORD_GROUPS: list[dict[str, Any]] = [
    {"groupName": "AI·기술", "keywords": ["인공지능", "AI", "ChatGPT", "LLM"]},
    {"groupName": "경제·금융", "keywords": ["주식", "코스피", "환율", "금리"]},
    {"groupName": "엔터테인먼트", "keywords": ["드라마", "영화", "아이돌", "K-POP"]},
    {"groupName": "생활·소비", "keywords": ["쿠팡", "배달", "부동산", "여행"]},
]
_MAX_GROUPS_PER_REQUEST = 5


async def fetch_naver_trends(
    keyword_groups: list[dict[str, Any]],
    *,
    days: int = 7,
) -> list[dict[str, Any]]:
    """DataLab API 호출. keyword_groups 5개씩 배치 처리."""
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        logger.warning("naver_datalab_credentials_missing")
        return []

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        for i in range(0, len(keyword_groups), _MAX_GROUPS_PER_REQUEST):
            batch = keyword_groups[i : i + _MAX_GROUPS_PER_REQUEST]
            try:
                resp = await client.post(
                    _DATALAB_URL,
                    headers={
                        "X-Naver-Client-Id": client_id,
                        "X-Naver-Client-Secret": client_secret,
                        "Content-Type": "application/json",
                    },
                    json={
                        "startDate": start_date.strftime("%Y-%m-%d"),
                        "endDate": end_date.strftime("%Y-%m-%d"),
                        "timeUnit": "date",
                        "keywordGroups": batch,
                        "device": "",
                        "ages": [],
                        "gender": "",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                results.extend(data.get("results", []))
                CRAWLER_REQUESTS.labels(source="naver_datalab", result="success").inc()
            except Exception as exc:
                CRAWLER_REQUESTS.labels(source="naver_datalab", result="failure").inc()
                logger.warning("naver_datalab_fetch_failed", batch_index=i, error=str(exc))

    return results


async def crawl_naver_datalab(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """DataLab 트렌드를 수집하여 sns_trend 테이블에 저장."""
    if not await check_quota("naver_datalab", db_pool):
        logger.info("naver_datalab_quota_exceeded")
        return []

    try:
        keyword_groups = await _build_keyword_groups(db_pool)
        results = await fetch_naver_trends(keyword_groups, days=7)
        if not results:
            return []

        await increment_quota("naver_datalab", db_pool)

        saved: list[dict[str, Any]] = []
        async with db_pool.acquire() as conn:
            for result in results:
                title = result.get("title", "")
                keywords = result.get("keywords", [])
                data_points = result.get("data", [])
                if not data_points:
                    continue

                recent_ratios = [p["ratio"] for p in data_points[-7:] if p.get("ratio")]
                score = sum(recent_ratios) / len(recent_ratios) if recent_ratios else 0.0

                await conn.execute(
                    """
                    INSERT INTO sns_trend
                        (platform, keyword, score, locale, raw_data)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    ON CONFLICT (platform, keyword, locale) DO UPDATE
                        SET score = EXCLUDED.score,
                            raw_data = EXCLUDED.raw_data,
                            snapshot_at = now()
                    """,
                    "naver_datalab",
                    title,
                    score,
                    "ko",
                    json.dumps({"keywords": keywords, "data": data_points[-7:]}),
                )
                saved.append({"keyword": title, "score": score})

        logger.info("naver_datalab_crawl_done", count=len(saved))
        return saved

    except Exception as exc:
        logger.warning("naver_datalab_crawl_failed", error=str(exc))
        return []


async def _build_keyword_groups(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """활성 news_group의 keywords로 DataLab 쿼리 그룹 동적 구성."""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT unnest(keywords) AS kw
                FROM news_group
                WHERE locale = 'ko'
                  AND created_at > now() - interval '24 hours'
                  AND score > 10
                LIMIT 50
                """,
            )
        keywords = [r["kw"] for r in rows if r["kw"]]
        if not keywords:
            return _DEFAULT_KEYWORD_GROUPS

        groups: list[dict[str, Any]] = []
        for i in range(0, len(keywords), 5):
            batch = keywords[i : i + 5]
            groups.append({"groupName": batch[0], "keywords": batch})
        return groups[:10]
    except Exception as exc:
        logger.warning("naver_datalab_build_groups_failed", error=str(exc))
        return _DEFAULT_KEYWORD_GROUPS
