"""Tests for personalization API (GET/PUT /api/v1/personalization).

Coverage targets:
- GET: returns defaults when no row exists, returns saved data
- PUT: upserts and returns updated data
- DB error handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from backend.api.routers.personalization import router
from backend.auth.dependencies import CurrentUser
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.db_pool = MagicMock()
    return app


def _patch_require_auth(user_id: str = "user-123", plan: str = "free", role: str = "general"):
    """Override require_auth dependency to return a mock CurrentUser."""

    async def _mock_require_auth() -> CurrentUser:
        return CurrentUser(user_id=user_id, plan=plan, role=role)

    return _mock_require_auth


# ---------------------------------------------------------------------------
# GET /api/v1/personalization
# ---------------------------------------------------------------------------


class TestGetPersonalization:
    def test_returns_defaults_when_no_row(self) -> None:
        app = _make_app()

        with (
            patch(
                "backend.api.routers.personalization.get_personalization",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.api.routers.personalization.require_auth",
                new=_patch_require_auth(),
            ),
        ):
            from backend.auth.dependencies import require_auth

            app.dependency_overrides[require_auth] = _patch_require_auth()
            client = TestClient(app)
            response = client.get("/api/v1/personalization")

        assert response.status_code == 200
        data = response.json()
        assert data["category_weights"] == {}
        assert data["locale_ratio"] == 0.5

    def test_returns_saved_data(self) -> None:
        app = _make_app()
        mock_row = {
            "category_weights": {"tech": 0.8, "sports": 0.2},
            "locale_ratio": 0.7,
        }

        with patch(
            "backend.api.routers.personalization.get_personalization",
            new=AsyncMock(return_value=mock_row),
        ):
            from backend.auth.dependencies import require_auth

            app.dependency_overrides[require_auth] = _patch_require_auth()
            client = TestClient(app)
            response = client.get("/api/v1/personalization")

        assert response.status_code == 200
        data = response.json()
        assert data["category_weights"] == {"tech": 0.8, "sports": 0.2}
        assert data["locale_ratio"] == 0.7

    def test_db_error_returns_500(self) -> None:
        app = _make_app()

        with patch(
            "backend.api.routers.personalization.get_personalization",
            new=AsyncMock(side_effect=Exception("DB connection failed")),
        ):
            from backend.auth.dependencies import require_auth

            app.dependency_overrides[require_auth] = _patch_require_auth()
            client = TestClient(app)
            response = client.get("/api/v1/personalization")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# PUT /api/v1/personalization
# ---------------------------------------------------------------------------


class TestPutPersonalization:
    def test_upserts_and_returns_data(self) -> None:
        app = _make_app()

        with patch(
            "backend.api.routers.personalization.upsert_personalization",
            new=AsyncMock(return_value=None),
        ):
            from backend.auth.dependencies import require_auth

            app.dependency_overrides[require_auth] = _patch_require_auth()
            client = TestClient(app)
            response = client.put(
                "/api/v1/personalization",
                json={"category_weights": {"tech": 0.9}, "locale_ratio": 0.6},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["category_weights"] == {"tech": 0.9}
        assert data["locale_ratio"] == 0.6

    def test_default_values_accepted(self) -> None:
        app = _make_app()

        with patch(
            "backend.api.routers.personalization.upsert_personalization",
            new=AsyncMock(return_value=None),
        ):
            from backend.auth.dependencies import require_auth

            app.dependency_overrides[require_auth] = _patch_require_auth()
            client = TestClient(app)
            response = client.put("/api/v1/personalization", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["category_weights"] == {}
        assert data["locale_ratio"] == 0.5

    def test_db_error_returns_500(self) -> None:
        app = _make_app()

        with patch(
            "backend.api.routers.personalization.upsert_personalization",
            new=AsyncMock(side_effect=Exception("DB connection failed")),
        ):
            from backend.auth.dependencies import require_auth

            app.dependency_overrides[require_auth] = _patch_require_auth()
            client = TestClient(app)
            response = client.put(
                "/api/v1/personalization",
                json={"category_weights": {}, "locale_ratio": 0.5},
            )

        assert response.status_code == 500

    def test_upsert_called_with_correct_args(self) -> None:
        app = _make_app()
        mock_upsert = AsyncMock(return_value=None)

        with patch(
            "backend.api.routers.personalization.upsert_personalization",
            new=mock_upsert,
        ):
            from backend.auth.dependencies import require_auth

            app.dependency_overrides[require_auth] = _patch_require_auth(user_id="user-456")
            client = TestClient(app)
            client.put(
                "/api/v1/personalization",
                json={"category_weights": {"sports": 0.5}, "locale_ratio": 0.3},
            )

        mock_upsert.assert_awaited_once()
        call_kwargs = mock_upsert.call_args
        assert call_kwargs.kwargs["user_id"] == "user-456"
        assert call_kwargs.kwargs["category_weights"] == {"sports": 0.5}
        assert call_kwargs.kwargs["locale_ratio"] == 0.3
