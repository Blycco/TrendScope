"""Tests for meta trends: cluster_groups_by_keywords + GET /api/v1/trends/meta."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.meta_clusterer import (
    MetaTrend,
    cluster_groups_by_keywords,
)
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Unit tests: cluster_groups_by_keywords
# ---------------------------------------------------------------------------


class TestClusterGroupsByKeywords:
    def test_empty_input_returns_empty(self) -> None:
        """빈 입력은 빈 리스트를 반환해야 한다."""
        result = cluster_groups_by_keywords([])
        assert result == []

    def test_same_category_overlapping_keywords_creates_cluster(self) -> None:
        """같은 category, 키워드 오버랩 그룹 3개 → MetaTrend 생성."""
        groups = [
            {
                "id": "id-1",
                "title": "AI 채용 급증",
                "category": "tech",
                "keywords": ["AI", "채용", "IT", "기술"],
                "score": 10.0,
            },
            {
                "id": "id-2",
                "title": "AI 스타트업 투자",
                "category": "tech",
                "keywords": ["AI", "스타트업", "투자", "기술"],
                "score": 8.0,
            },
            {
                "id": "id-3",
                "title": "AI 기술 트렌드",
                "category": "tech",
                "keywords": ["AI", "기술", "트렌드", "미래"],
                "score": 6.0,
            },
        ]
        result = cluster_groups_by_keywords(groups, threshold=0.1, min_cluster_size=2)
        assert len(result) >= 1
        assert isinstance(result[0], MetaTrend)
        # meta_title은 score 최고 그룹 (id-1)의 title
        assert result[0].meta_title == "AI 채용 급증"
        # sub_trend_ids에 모든 id 포함
        for gid in ["id-1", "id-2", "id-3"]:
            assert gid in result[0].sub_trend_ids
        # keywords는 10개 이하
        assert len(result[0].keywords) <= 10
        # total_score 합산 확인
        assert result[0].total_score == pytest.approx(24.0)

    def test_different_categories_no_cross_cluster(self) -> None:
        """각 다른 category, 단독 그룹 → min_cluster_size=2로 [] 반환."""
        groups = [
            {
                "id": "id-1",
                "title": "IT 뉴스",
                "category": "tech",
                "keywords": ["AI", "기술"],
                "score": 5.0,
            },
            {
                "id": "id-2",
                "title": "경제 뉴스",
                "category": "economy",
                "keywords": ["주식", "금리"],
                "score": 4.0,
            },
            {
                "id": "id-3",
                "title": "사회 뉴스",
                "category": "society",
                "keywords": ["교육", "복지"],
                "score": 3.0,
            },
        ]
        result = cluster_groups_by_keywords(groups, threshold=0.2, min_cluster_size=2)
        assert result == []

    def test_result_sorted_by_total_score_desc(self) -> None:
        """결과가 total_score 내림차순으로 정렬되어야 한다."""
        groups = [
            {
                "id": "id-a1",
                "title": "저점수 A1",
                "category": "cat_a",
                "keywords": ["kw1", "kw2", "kw3"],
                "score": 1.0,
            },
            {
                "id": "id-a2",
                "title": "저점수 A2",
                "category": "cat_a",
                "keywords": ["kw1", "kw2", "kw4"],
                "score": 2.0,
            },
            {
                "id": "id-b1",
                "title": "고점수 B1",
                "category": "cat_b",
                "keywords": ["kw5", "kw6", "kw7"],
                "score": 50.0,
            },
            {
                "id": "id-b2",
                "title": "고점수 B2",
                "category": "cat_b",
                "keywords": ["kw5", "kw6", "kw8"],
                "score": 60.0,
            },
        ]
        result = cluster_groups_by_keywords(groups, threshold=0.1, min_cluster_size=2)
        assert len(result) == 2
        assert result[0].total_score > result[1].total_score

    def test_min_cluster_size_respected(self) -> None:
        """min_cluster_size=3이면 2개 그룹 클러스터는 제외된다."""
        groups = [
            {
                "id": "id-1",
                "title": "트렌드 1",
                "category": "tech",
                "keywords": ["AI", "기술", "미래"],
                "score": 5.0,
            },
            {
                "id": "id-2",
                "title": "트렌드 2",
                "category": "tech",
                "keywords": ["AI", "기술", "혁신"],
                "score": 5.0,
            },
        ]
        result = cluster_groups_by_keywords(groups, threshold=0.1, min_cluster_size=3)
        assert result == []


# ---------------------------------------------------------------------------
# Integration tests: GET /api/v1/trends/meta
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-meta")


@pytest.fixture
async def meta_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
        patch(
            "backend.api.routers.meta_trends.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("backend.api.routers.meta_trends.set_cached", new_callable=AsyncMock),
        patch(
            "backend.api.routers.meta_trends.fetch_groups_for_meta",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


class TestGetMetaTrends:
    async def test_returns_200(self, meta_client: AsyncClient) -> None:
        """GET /api/v1/trends/meta → 200."""
        resp = await meta_client.get("/api/v1/trends/meta")
        assert resp.status_code == 200

    async def test_returns_items_array(self, meta_client: AsyncClient) -> None:
        """응답에 items 배열이 포함되어야 한다."""
        resp = await meta_client.get("/api/v1/trends/meta")
        body = resp.json()
        assert "items" in body
        assert isinstance(body["items"], list)

    async def test_locale_query_param(self, meta_client: AsyncClient) -> None:
        """GET /api/v1/trends/meta?locale=ko → 200."""
        resp = await meta_client.get("/api/v1/trends/meta?locale=ko")
        assert resp.status_code == 200
        body = resp.json()
        assert body["locale"] == "ko"

    async def test_total_field_matches_items_length(self, meta_client: AsyncClient) -> None:
        """total 필드가 items 길이와 일치해야 한다."""
        resp = await meta_client.get("/api/v1/trends/meta")
        body = resp.json()
        assert body["total"] == len(body["items"])

    async def test_cache_hit_returns_cached(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """캐시 히트 시 DB 조회 없이 캐시 데이터를 반환해야 한다."""
        from backend.api.main import create_app

        cached_data = json.dumps({"items": [], "locale": None, "total": 0}).encode()

        app = create_app()
        app.state.db_pool = mock_db_pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch("backend.api.middleware.rate_limit.get_redis", return_value=mock_redis),
            patch(
                "backend.api.routers.meta_trends.get_cached",
                new_callable=AsyncMock,
                return_value=cached_data,
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/trends/meta")
        assert resp.status_code == 200
