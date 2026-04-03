"""Tests for backend.api.routers.dashboard and backend.db.queries.dashboard."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from backend.api.routers.dashboard import get_dashboard_summary


def _mock_request(pool: MagicMock) -> MagicMock:
    req = MagicMock()
    req.app.state.db_pool = pool
    return req


class TestGetDashboardSummary:
    async def test_returns_summary_from_db(self) -> None:
        mock_data = {
            "total_trends": 42,
            "total_news": 156,
            "avg_score": 18.3,
            "top_category": "tech",
            "early_signal_count": 7,
            "category_counts": {"tech": 15, "economy": 10, "society": 8},
            "source_counts": {"news": 80, "community": 30, "sns": 20},
        }
        pool = MagicMock()
        req = _mock_request(pool)

        with (
            patch(
                "backend.api.routers.dashboard.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.api.routers.dashboard.set_cached",
                AsyncMock(),
            ),
            patch(
                "backend.api.routers.dashboard.fetch_dashboard_summary",
                AsyncMock(return_value=mock_data),
            ),
        ):
            resp = await get_dashboard_summary(req)
            assert resp.status_code == 200
            import json

            body = json.loads(resp.body)
            assert body["total_trends"] == 42
            assert body["total_news"] == 156
            assert body["avg_score"] == 18.3
            assert body["top_category"] == "tech"
            assert body["early_signal_count"] == 7
            assert body["category_counts"]["tech"] == 15
            assert body["source_counts"]["news"] == 80

    async def test_returns_cached_response(self) -> None:
        cached_body = (
            b'{"total_trends":10,"total_news":50,"avg_score":12.0,'
            b'"top_category":"economy","early_signal_count":3,'
            b'"category_counts":{"economy":10},'
            b'"source_counts":{"news":50}}'
        )
        pool = MagicMock()
        req = _mock_request(pool)

        with patch(
            "backend.api.routers.dashboard.get_cached",
            AsyncMock(return_value=cached_body),
        ):
            resp = await get_dashboard_summary(req)
            assert resp.status_code == 200
            assert resp.body == cached_body

    async def test_returns_500_on_db_error(self) -> None:
        pool = MagicMock()
        req = _mock_request(pool)

        with (
            patch(
                "backend.api.routers.dashboard.get_cached",
                AsyncMock(return_value=None),
            ),
            patch(
                "backend.api.routers.dashboard.fetch_dashboard_summary",
                AsyncMock(side_effect=RuntimeError("db connection lost")),
            ),
        ):
            resp = await get_dashboard_summary(req)
            assert resp.status_code == 500
