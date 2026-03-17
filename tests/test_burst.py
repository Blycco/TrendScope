"""Tests for burst detection module."""

from __future__ import annotations

import time

from backend.processor.algorithms.burst import (
    BurstLevel,
    BurstResult,
    TimeSeriesPoint,
    _classify_level,
    _percentile_anomaly_score,
    _statistical_anomaly_score,
    compute_cusum_score,
    compute_prophet_score,
    detect_burst,
)


def _make_series(values: list[float], interval_sec: float = 60.0) -> list[TimeSeriesPoint]:
    """Helper to create a time series from values."""
    base_ts = time.time() - len(values) * interval_sec
    return [
        TimeSeriesPoint(timestamp=base_ts + i * interval_sec, value=v) for i, v in enumerate(values)
    ]


class TestClassifyLevel:
    """Tests for burst level classification."""

    def test_mega(self) -> None:
        assert _classify_level(0.95) == BurstLevel.MEGA

    def test_high(self) -> None:
        assert _classify_level(0.80) == BurstLevel.HIGH

    def test_normal(self) -> None:
        assert _classify_level(0.65) == BurstLevel.NORMAL

    def test_low(self) -> None:
        assert _classify_level(0.45) == BurstLevel.LOW

    def test_end(self) -> None:
        assert _classify_level(0.10) == BurstLevel.END

    def test_boundary_mega(self) -> None:
        assert _classify_level(0.91) == BurstLevel.MEGA

    def test_boundary_end(self) -> None:
        assert _classify_level(0.29) == BurstLevel.END


class TestStatisticalAnomalyScore:
    """Tests for statistical fallback."""

    def test_too_few_points(self) -> None:
        assert _statistical_anomaly_score([1.0, 2.0]) == 0.0

    def test_constant_with_spike(self) -> None:
        values = [10.0] * 10 + [100.0]
        score = _statistical_anomaly_score(values)
        assert score > 0.5

    def test_constant_values(self) -> None:
        values = [5.0] * 10
        score = _statistical_anomaly_score(values)
        # Latest equals mean, std=0 → latest > mean is False → returns 0.0
        assert score == 0.0

    def test_normal_value(self) -> None:
        values = [10.0, 11.0, 9.0, 10.5, 9.5, 10.0]
        score = _statistical_anomaly_score(values)
        assert 0.0 <= score <= 1.0


class TestPercentileAnomalyScore:
    """Tests for percentile fallback."""

    def test_too_few_points(self) -> None:
        assert _percentile_anomaly_score([1.0]) == 0.0

    def test_highest_value(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        score = _percentile_anomaly_score(values)
        assert score > 0.5

    def test_lowest_value(self) -> None:
        values = [100.0, 200.0, 300.0, 1.0]
        score = _percentile_anomaly_score(values)
        assert score < 0.5


class TestCusumScore:
    """Tests for CUSUM computation."""

    def test_too_few_points(self) -> None:
        series = _make_series([1.0, 2.0])
        assert compute_cusum_score(series) == 0.0

    def test_constant_series(self) -> None:
        series = _make_series([10.0] * 20)
        score = compute_cusum_score(series)
        assert score == 0.0  # No change

    def test_spike_detected(self) -> None:
        values = [10.0] * 15 + [100.0, 200.0, 300.0]
        series = _make_series(values)
        score = compute_cusum_score(series)
        assert score > 0.0


class TestProphetScore:
    """Tests for Prophet score (uses statistical fallback since Prophet not installed)."""

    def test_too_few_points(self) -> None:
        series = _make_series([1.0, 2.0])
        assert compute_prophet_score(series) == 0.0

    def test_spike_detection_fallback(self) -> None:
        values = [10.0] * 10 + [100.0]
        series = _make_series(values)
        score = compute_prophet_score(series)
        assert score > 0.5


class TestDetectBurst:
    """Tests for the ensemble burst detection."""

    def test_too_few_points(self) -> None:
        series = _make_series([1.0])
        result = detect_burst(series)
        assert isinstance(result, BurstResult)
        assert result.score == 0.0
        assert result.level == BurstLevel.END

    def test_stable_series(self) -> None:
        series = _make_series([10.0] * 20)
        result = detect_burst(series)
        assert result.level in (BurstLevel.END, BurstLevel.LOW)

    def test_spike_series(self) -> None:
        values = [10.0] * 15 + [500.0, 1000.0, 2000.0]
        series = _make_series(values)
        result = detect_burst(series)
        assert result.score > 0.0
        assert result.prophet_score >= 0.0
        assert result.iforest_score >= 0.0
        assert result.cusum_score >= 0.0

    def test_result_structure(self) -> None:
        series = _make_series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = detect_burst(series)
        assert hasattr(result, "score")
        assert hasattr(result, "level")
        assert hasattr(result, "prophet_score")
        assert hasattr(result, "iforest_score")
        assert hasattr(result, "cusum_score")

    def test_ensemble_weights(self) -> None:
        # Verify the ensemble math: 0.40*p + 0.35*i + 0.25*c
        series = _make_series([10.0] * 10 + [100.0])
        result = detect_burst(series)
        expected = (
            0.40 * result.prophet_score + 0.35 * result.iforest_score + 0.25 * result.cusum_score
        )
        assert abs(result.score - expected) < 0.001
