"""Tests for trend forecast module and API router."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.prediction import (
    TimeSeriesPoint,
    _forecast_linear,
    forecast_trend,
)


def _make_series(values: list[float], start_days_ago: int = 90) -> list[TimeSeriesPoint]:
    now = datetime.now(timezone.utc)
    return [
        TimeSeriesPoint(
            ds=now - timedelta(days=start_days_ago - i),
            y=v,
        )
        for i, v in enumerate(values)
    ]


class TestForecastLinear:
    def test_returns_correct_horizon(self) -> None:
        series = _make_series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = _forecast_linear(series, horizon_days=30)
        assert len(result) == 30

    def test_returns_dict_with_expected_keys(self) -> None:
        series = _make_series([1, 2, 3, 4, 5])
        result = _forecast_linear(series, horizon_days=7)
        for point in result:
            assert "date" in point
            assert "yhat" in point
            assert "yhat_lower" in point
            assert "yhat_upper" in point

    def test_rising_trend_extrapolates_upward(self) -> None:
        series = _make_series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = _forecast_linear(series, horizon_days=10)
        # First forecast point should be above the last actual value
        assert result[0]["yhat"] > 10.0

    def test_declining_trend_values_clamped_to_zero(self) -> None:
        series = _make_series([100, 80, 60, 40, 20, 10, 5, 2, 1, 0.5])
        result = _forecast_linear(series, horizon_days=365)
        for point in result:
            assert point["yhat"] >= 0.0
            assert point["yhat_lower"] >= 0.0
            assert point["yhat_upper"] >= 0.0

    def test_flat_trend(self) -> None:
        series = _make_series([5, 5, 5, 5, 5, 5, 5, 5])
        result = _forecast_linear(series, horizon_days=30)
        for point in result:
            assert abs(point["yhat"] - 5.0) < 1.0

    def test_confidence_band_widens_over_time(self) -> None:
        series = _make_series([1, 3, 2, 4, 3, 5, 4, 6, 5, 7])
        result = _forecast_linear(series, horizon_days=60)
        first_band = result[0]["yhat_upper"] - result[0]["yhat_lower"]
        last_band = result[-1]["yhat_upper"] - result[-1]["yhat_lower"]
        assert last_band >= first_band

    def test_dates_are_sequential(self) -> None:
        series = _make_series([1, 2, 3, 4, 5])
        result = _forecast_linear(series, horizon_days=10)
        dates = [datetime.strptime(p["date"], "%Y-%m-%d") for p in result]
        for i in range(1, len(dates)):
            assert dates[i] - dates[i - 1] == timedelta(days=1)

    def test_constant_series_zero_denom(self) -> None:
        """When all y-values are constant but x-variance is non-zero, should still work."""
        series = _make_series([3, 3, 3, 3, 3])
        result = _forecast_linear(series, horizon_days=5)
        assert len(result) == 5
        for point in result:
            assert abs(point["yhat"] - 3.0) < 0.01


class TestForecastTrend:
    @pytest.mark.asyncio
    async def test_insufficient_data_returns_empty(self) -> None:
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await forecast_trend("some-group-id", mock_pool, horizon_days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_uses_linear_fallback(self) -> None:
        series = _make_series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        with patch(
            "backend.processor.algorithms.prediction.TrendPredictor.build_series",
            new_callable=AsyncMock,
            return_value=series,
        ):
            result = await forecast_trend("group-id", MagicMock(), horizon_days=30)
            assert len(result) == 30
            assert all("date" in p for p in result)

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self) -> None:
        with patch(
            "backend.processor.algorithms.prediction.TrendPredictor.build_series",
            new_callable=AsyncMock,
            side_effect=Exception("DB error"),
        ):
            result = await forecast_trend("group-id", MagicMock(), horizon_days=30)
            assert result == []


class TestForecastSchema:
    def test_forecast_response_schema(self) -> None:
        from backend.api.schemas.forecast import ForecastPoint, ForecastResponse

        point = ForecastPoint(date="2026-01-01", yhat=5.0, yhat_lower=3.0, yhat_upper=7.0)
        assert point.date == "2026-01-01"

        resp = ForecastResponse(group_id="abc", horizon_days=365, points=[point])
        assert resp.group_id == "abc"
        assert len(resp.points) == 1
