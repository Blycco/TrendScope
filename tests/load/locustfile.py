"""Locust 부하 테스트 — MAU 1,000 시뮬레이션."""

from __future__ import annotations

import random

from locust import HttpUser, between, task


class TrendScopeUser(HttpUser):
    """일반 사용자 — 트렌드 피드, 인사이트, 스크랩 위주."""

    wait_time = between(1, 3)
    weight = 80  # 80% 비율

    def on_start(self) -> None:
        """로그인 후 토큰 저장."""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "testpass123"},
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        else:
            self.token = ""
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def view_trends(self) -> None:
        self.client.get("/api/v1/trends", headers=self.headers)

    @task(3)
    def view_insights(self) -> None:
        self.client.get("/api/v1/insights", headers=self.headers)

    @task(2)
    def scrap_item(self) -> None:
        group_id = random.randint(1, 100)  # noqa: S311
        self.client.post(
            "/api/v1/scraps",
            json={"group_id": group_id},
            headers=self.headers,
        )


class PowerUser(HttpUser):
    """파워 유저 — 검색 및 내보내기."""

    wait_time = between(2, 5)
    weight = 20  # 20% 비율

    def on_start(self) -> None:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "power@example.com", "password": "testpass123"},
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        else:
            self.token = ""
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def search_trends(self) -> None:
        keyword = random.choice(["AI", "GPT", "SvelteKit", "FastAPI", "Python"])  # noqa: S311
        self.client.get(f"/api/v1/trends?search={keyword}", headers=self.headers)

    @task(1)
    def export_data(self) -> None:
        self.client.get("/api/v1/insights/export", headers=self.headers)
