"""Tests for trend prediction module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.processor.algorithms.prediction import (
    PredictionResult,
    TimeSeriesPoint,
    TrendDirection,
    TrendPredictor,
)


def _make_series(values: list[float], start_days_ago: int = 30) -> list[TimeSeriesPoint]:
    now = datetime.now(timezone.utc)
    return [
        TimeSeriesPoint(
            ds=now - timedelta(days=start_days_ago - i),
            y=v,
        )
        for i, v in enumerate(values)
    ]


class TestTrendPredictor:
    def test_insufficient_data_returns_stable(self) -> None:
        predictor = TrendPredictor()
        series = _make_series([5.0, 10.0])
        result = predictor.predict(series)
        assert isinstance(result, PredictionResult)
        assert result.confidence == 0.0
        assert result.trend_direction == TrendDirection.STABLE

    def test_empty_series(self) -> None:
        predictor = TrendPredictor()
        result = predictor.predict([])
        assert result.predicted_peak == 0.0
        assert result.confidence == 0.0

    def test_linear_fallback_rising(self) -> None:
        predictor = TrendPredictor(horizon_hours=72)
        series = _make_series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = predictor._predict_linear(series)
        assert result.predicted_peak > 10.0
        assert result.trend_direction == TrendDirection.RISING
        assert result.confidence == 0.3

    def test_linear_fallback_declining(self) -> None:
        predictor = TrendPredictor(horizon_hours=72)
        series = _make_series([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])
        result = predictor._predict_linear(series)
        assert result.trend_direction == TrendDirection.DECLINING

    def test_linear_flat_returns_stable(self) -> None:
        predictor = TrendPredictor()
        series = _make_series([5, 5, 5, 5, 5, 5, 5, 5])
        result = predictor._predict_linear(series)
        assert result.trend_direction == TrendDirection.STABLE

    def test_predict_uses_linear_when_prophet_unavailable(self) -> None:
        predictor = TrendPredictor()
        series = _make_series([1, 2, 3, 4, 5])
        result = predictor.predict(series)
        assert isinstance(result, PredictionResult)
        assert result.horizon_hours == 72

    def test_determine_direction(self) -> None:
        assert TrendPredictor._determine_direction(10, 15) == TrendDirection.RISING
        assert TrendPredictor._determine_direction(10, 5) == TrendDirection.DECLINING
        assert TrendPredictor._determine_direction(10, 10.5) == TrendDirection.STABLE
        assert TrendPredictor._determine_direction(0, 5) == TrendDirection.RISING
        assert TrendPredictor._determine_direction(0, 0) == TrendDirection.STABLE
