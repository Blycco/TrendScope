"""Tests for keyword history: save_keyword_snapshot, fetch_keyword_history,
GET /api/v1/trends/{id}/keywords/history.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Unit tests: save_keyword_snapshot
# ---------------------------------------------------------------------------


class TestSaveKeywordSnapshot:
    async def test_calls_executemany_with_correct_params(self) -> None:
        """save_keyword_snapshot이 executemany를 올바른 인자로 호출해야 한다."""
        from backend.db.queries.keyword_history import save_keyword_snapshot

        pool = MagicMock()
        conn = AsyncMock()
        conn.executemany = AsyncMock()
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        group_id = "00000000-0000-0000-0000-000000000001"
        keywords = [("AI", 3), ("트렌드", 2)]

        await save_keyword_snapshot(pool, group_id, keywords)

        conn.executemany.assert_called_once()
        call_args = conn.executemany.call_args
        sql = call_args[0][0]
        assert "INSERT INTO keyword_snapshot" in sql
        rows = call_args[0][1]
        assert len(rows) == 2
        assert rows[0] == (group_id, "AI", 3)
        assert rows[1] == (group_id, "트렌드", 2)

    async def test_empty_keywords_skips_db_call(self) -> None:
        """keywords가 빈 리스트이면 DB 호출을 하지 않아야 한다."""
        from backend.db.queries.keyword_history import save_keyword_snapshot

        pool = MagicMock()
        pool.acquire = MagicMock()

        await save_keyword_snapshot(pool, "some-id", [])

        pool.acquire.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests: fetch_keyword_history
# ---------------------------------------------------------------------------


class TestFetchKeywordHistory:
    async def test_empty_db_returns_empty_list(self) -> None:
        """DB에 스냅샷이 없으면 빈 리스트를 반환해야 한다."""
        from backend.db.queries.keyword_history import fetch_keyword_history

        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        result = await fetch_keyword_history(pool, "some-id")
        assert result == []

    async def test_groups_rows_by_snapshot_at(self) -> None:
        """스냅샷 2개의 rows를 snapshot_at 기준으로 그룹핑해야 한다."""
        from backend.db.queries.keyword_history import fetch_keyword_history

        t1 = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 4, 8, 6, 0, 0, tzinfo=timezone.utc)

        def _make_row(keyword: str, frequency: int, snap_at: datetime) -> MagicMock:
            row = MagicMock()
            row.__getitem__ = lambda self, k: {
                "keyword": keyword,
                "frequency": frequency,
                "snapshot_at": snap_at,
            }[k]
            return row

        rows = [
            _make_row("AI", 5, t1),
            _make_row("기술", 3, t1),
            _make_row("트렌드", 4, t2),
        ]

        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=rows)
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        result = await fetch_keyword_history(pool, "some-id")

        assert len(result) == 2
        # 최신 스냅샷이 먼저
        assert result[0]["snapshot_at"] == t1.isoformat()
        assert len(result[0]["top_keywords"]) == 2
        assert result[1]["snapshot_at"] == t2.isoformat()
        assert len(result[1]["top_keywords"]) == 1

    async def test_error_returns_empty_list(self) -> None:
        """DB 오류 시 빈 리스트를 반환해야 한다 (예외를 전파하지 않음)."""
        from backend.db.queries.keyword_history import fetch_keyword_history

        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("DB error"))
        pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        result = await fetch_keyword_history(pool, "some-id")
        assert result == []


# ---------------------------------------------------------------------------
# Integration tests: GET /api/v1/trends/{id}/keywords/history
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-kw-history")


@pytest.fixture
async def history_client(mock_db_pool: MagicMock, mock_redis: AsyncMock) -> AsyncClient:
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
            "backend.api.routers.meta_trends.fetch_keyword_history",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


class TestGetKeywordHistory:
    async def test_returns_200_snapshots_array(self, history_client: AsyncClient) -> None:
        """GET /api/v1/trends/{id}/keywords/history → 200, snapshots 배열."""
        resp = await history_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000001/keywords/history"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "snapshots" in body
        assert isinstance(body["snapshots"], list)

    async def test_empty_snapshots_returns_200(self, history_client: AsyncClient) -> None:
        """스냅샷 없음 → 200, snapshots=[]."""
        resp = await history_client.get(
            "/api/v1/trends/00000000-0000-0000-0000-000000000002/keywords/history"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["snapshots"] == []

    async def test_group_id_in_response(self, history_client: AsyncClient) -> None:
        """응답에 요청한 group_id가 포함되어야 한다."""
        group_id = "00000000-0000-0000-0000-000000000003"
        resp = await history_client.get(f"/api/v1/trends/{group_id}/keywords/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["group_id"] == group_id

    async def test_cache_hit_skips_db(self, mock_db_pool: MagicMock, mock_redis: AsyncMock) -> None:
        """캐시 히트 시 DB 조회 없이 캐시 데이터를 반환해야 한다."""
        from backend.api.main import create_app

        group_id = "00000000-0000-0000-0000-000000000004"
        cached_data = json.dumps({"group_id": group_id, "snapshots": []}).encode()

        app = create_app()
        app.state.db_pool = mock_db_pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch(
                "backend.api.middleware.rate_limit.get_redis",
                return_value=mock_redis,
            ),
            patch(
                "backend.api.routers.meta_trends.get_cached",
                new_callable=AsyncMock,
                return_value=cached_data,
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/v1/trends/{group_id}/keywords/history")

        assert resp.status_code == 200

    async def test_snapshots_with_data(
        self, mock_db_pool: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """스냅샷 데이터가 있을 때 올바른 구조로 반환해야 한다."""
        from backend.api.main import create_app

        snapshot_data = [
            {
                "snapshot_at": "2026-04-08T12:00:00+00:00",
                "top_keywords": [
                    {"term": "AI", "frequency": 5},
                    {"term": "기술", "frequency": 3},
                ],
            }
        ]

        app = create_app()
        app.state.db_pool = mock_db_pool

        with (
            patch("backend.api.routers.health.get_redis", return_value=mock_redis),
            patch(
                "backend.api.middleware.rate_limit.get_redis",
                return_value=mock_redis,
            ),
            patch(
                "backend.api.routers.meta_trends.get_cached",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.routers.meta_trends.set_cached",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.api.routers.meta_trends.fetch_keyword_history",
                new_callable=AsyncMock,
                return_value=snapshot_data,
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(
                    "/api/v1/trends/00000000-0000-0000-0000-000000000005/keywords/history"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["snapshots"]) == 1
        snap = body["snapshots"][0]
        assert snap["snapshot_at"] == "2026-04-08T12:00:00+00:00"
        assert len(snap["top_keywords"]) == 2
        assert snap["top_keywords"][0]["term"] == "AI"
        assert snap["top_keywords"][0]["frequency"] == 5
