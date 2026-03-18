"""Tests for GET /api/v1/trends/{keyword}/insights endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.api.middleware.quota import check_insight_quota
from backend.api.middleware.rate_limit import rate_limit_check
from backend.auth.dependencies import CurrentUser, require_auth
from backend.processor.shared.ai_config import AIConfig
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr


def _make_pro_user(role: str = "general") -> CurrentUser:
    return CurrentUser(user_id="user-pro-001", plan="pro", role=role)


def _make_free_user() -> CurrentUser:
    return CurrentUser(user_id="user-free-001", plan="free", role="general")


def _make_ai_config() -> AIConfig:
    return AIConfig(
        provider="textrank",
        model="textrank",
        api_key=SecretStr(""),
        max_tokens=512,
        temperature=0.0,
        fallback_provider="textrank",
    )


def _make_engine_result(
    role: str = "general",
    cached: bool = False,
    degraded: bool = False,
) -> dict:
    content_map = {
        "marketer": {"ad_opportunities": ["광고 기회 1"], "source_urls": []},
        "creator": {
            "title_drafts": ["제목 1"],
            "timing": "월요일 오전",
            "seo_keywords": ["AI"],
            "source_urls": [],
        },
        "owner": {
            "consumer_reactions": ["반응 1"],
            "product_hints": ["힌트 1"],
            "market_ops": ["기회 1"],
            "source_urls": [],
        },
        "general": {"sns_drafts": ["SNS 글 1"], "engagement_methods": ["팁 1"], "source_urls": []},
    }
    return {
        "cached": cached,
        "degraded": degraded,
        "content": content_map.get(role, content_map["general"]),
    }


@pytest.fixture
async def insights_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
    """Client with pro user, all deps mocked, engine mocked."""
    from backend.api.main import create_app

    app = create_app()
    app.state.db_pool = mock_db_pool

    pro_user = _make_pro_user()
    app.dependency_overrides[require_auth] = lambda: pro_user
    app.dependency_overrides[rate_limit_check] = lambda: pro_user
    app.dependency_overrides[check_insight_quota] = lambda: pro_user

    with (
        patch("backend.api.routers.health.get_redis", return_value=mock_redis),
        patch(
            "backend.api.routers.insights.get_ai_config",
            new=AsyncMock(return_value=_make_ai_config()),
        ),
        patch(
            "backend.api.routers.insights.fetch_news_for_keyword",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "backend.api.routers.insights.fetch_sns_for_keyword",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "backend.api.routers.insights.write_audit_log",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "backend.api.routers.insights.increment_insight_usage",
            new=AsyncMock(return_value=None),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


class TestGetTrendInsightsAuth:
    async def test_unauthenticated_returns_401(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        with patch("backend.api.routers.health.get_redis", return_value=mock_redis):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/trends/AI/insights")

        assert resp.status_code == 401

    async def test_free_plan_returns_402(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        free_user = _make_free_user()
        app.dependency_overrides[require_auth] = lambda: free_user

        with patch("backend.api.routers.health.get_redis", return_value=mock_redis):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/trends/AI/insights")

        app.dependency_overrides.clear()
        assert resp.status_code == 402


class TestGetTrendInsightsCacheMiss:
    async def test_general_role_generates_insights(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("general", cached=False, degraded=False)
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=general")

        assert resp.status_code == 200
        data = resp.json()
        assert data["keyword"] == "AI"
        assert data["role"] == "general"
        assert data["cached"] is False
        assert "content" in data

    async def test_marketer_role_generates_insights(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("marketer")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=marketer")

        assert resp.status_code == 200
        assert resp.json()["role"] == "marketer"

    async def test_creator_role_generates_insights(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("creator")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=creator")

        assert resp.status_code == 200
        assert resp.json()["role"] == "creator"

    async def test_owner_role_generates_insights(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("owner")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=owner")

        assert resp.status_code == 200
        assert resp.json()["role"] == "owner"

    async def test_cached_flag_false_on_miss(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("general", cached=False)
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights")

        assert resp.status_code == 200
        assert resp.json()["cached"] is False

    async def test_degraded_flag_forwarded(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("general", degraded=True)
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights")

        assert resp.status_code == 200
        assert resp.json()["degraded"] is True

    async def test_url_encoded_keyword_decoded(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("general")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            url = "/api/v1/trends/%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5/insights"
            resp = await insights_client.get(url)

        assert resp.status_code == 200
        assert resp.json()["keyword"] == "인공지능"


class TestGetTrendInsightsCacheHit:
    async def test_cache_hit_returns_immediately(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("general", cached=True)
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights")

        assert resp.status_code == 200
        assert resp.json()["cached"] is True


class TestGetTrendInsightsErrors:
    async def test_engine_exception_returns_500(self, insights_client: AsyncClient) -> None:
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(side_effect=RuntimeError("AI engine failure")),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights")

        assert resp.status_code == 500

    async def test_db_fetch_error_returns_500(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        from backend.api.main import create_app

        app = create_app()
        app.state.db_pool = mock_db_pool

        pro_user = _make_pro_user()
        app.dependency_overrides[require_auth] = lambda: pro_user
        app.dependency_overrides[rate_limit_check] = lambda: pro_user
        app.dependency_overrides[check_insight_quota] = lambda: pro_user

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch(
                "backend.api.routers.insights.get_ai_config",
                new=AsyncMock(return_value=_make_ai_config()),
            ),
            patch(
                "backend.api.routers.insights.fetch_news_for_keyword",
                new=AsyncMock(side_effect=RuntimeError("DB 오류")),
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/v1/trends/AI/insights")

        app.dependency_overrides.clear()
        assert resp.status_code == 500


class TestParseContent:
    async def test_parse_content_marketer_structure(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("marketer")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=marketer")

        assert resp.status_code == 200
        content = resp.json()["content"]
        assert "ad_opportunities" in content
        assert "source_urls" in content

    async def test_parse_content_creator_structure(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("creator")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=creator")

        assert resp.status_code == 200
        content = resp.json()["content"]
        assert "title_drafts" in content
        assert "timing" in content
        assert "seo_keywords" in content

    async def test_parse_content_owner_structure(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("owner")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=owner")

        assert resp.status_code == 200
        content = resp.json()["content"]
        assert "consumer_reactions" in content
        assert "product_hints" in content
        assert "market_ops" in content

    async def test_parse_content_general_structure(self, insights_client: AsyncClient) -> None:
        engine_result = _make_engine_result("general")
        with patch(
            "backend.api.routers.insights.ActionInsightEngine.generate",
            new=AsyncMock(return_value=engine_result),
        ):
            resp = await insights_client.get("/api/v1/trends/AI/insights?role=general")

        assert resp.status_code == 200
        content = resp.json()["content"]
        assert "sns_drafts" in content
        assert "engagement_methods" in content
