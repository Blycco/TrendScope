"""Tests for seasonality detection module."""

from __future__ import annotations

from datetime import datetime

from backend.processor.algorithms.seasonality import detect_seasonality


class TestDetectSeasonality:
    """Tests for detect_seasonality."""

    def test_empty_history_returns_false(self) -> None:
        assert detect_seasonality("test", []) is False

    def test_too_few_points_returns_false(self) -> None:
        history = [
            (datetime(2025, 1, 6, 10, 0), 5.0),
            (datetime(2025, 1, 13, 10, 0), 5.0),
        ]
        assert detect_seasonality("test", history) is False

    def test_single_point_returns_false(self) -> None:
        history = [(datetime(2025, 1, 6, 10, 0), 5.0)]
        assert detect_seasonality("test", history) is False

    def test_seasonal_pattern_detected(self) -> None:
        """Same week-of-year across multiple years with similar values."""
        # Week 2 across 3 years + current
        history = [
            (datetime(2023, 1, 9, 10, 0), 10.0),  # week 2, 2023
            (datetime(2024, 1, 8, 10, 0), 11.0),  # week 2, 2024
            (datetime(2025, 1, 6, 10, 0), 10.5),  # week 2, 2025
        ]
        # Current value (10.5) is within mean(10, 11) +/- 1*std
        assert detect_seasonality("holiday", history) is True

    def test_non_seasonal_spike(self) -> None:
        """Current value far outside historical range for that week."""
        history = [
            (datetime(2023, 1, 9, 10, 0), 2.0),  # week 2, 2023
            (datetime(2024, 1, 8, 10, 0), 3.0),  # week 2, 2024
            (datetime(2025, 1, 6, 10, 0), 50.0),  # week 2, 2025 — way above
        ]
        assert detect_seasonality("breaking_news", history) is False

    def test_no_matching_week_returns_false(self) -> None:
        """History exists but not for the current week-of-year."""
        history = [
            (datetime(2023, 3, 15, 10, 0), 10.0),  # week 11
            (datetime(2024, 3, 15, 10, 0), 10.0),  # week 11
            (datetime(2025, 1, 6, 10, 0), 10.0),  # week 2 — different
        ]
        assert detect_seasonality("test", history) is False

    def test_exact_same_values_seasonal(self) -> None:
        """Identical values at same week across years is clearly seasonal."""
        history = [
            (datetime(2023, 6, 12, 10, 0), 7.0),  # week 24
            (datetime(2024, 6, 10, 10, 0), 7.0),  # week 24
            (datetime(2025, 6, 9, 10, 0), 7.0),  # week 24
        ]
        assert detect_seasonality("summer_sale", history) is True

    def test_zero_std_exact_match(self) -> None:
        """When all past values are identical and current matches."""
        history = [
            (datetime(2023, 6, 12, 10, 0), 5.0),
            (datetime(2024, 6, 10, 10, 0), 5.0),
            (datetime(2025, 6, 9, 10, 0), 5.0),
        ]
        assert detect_seasonality("stable", history) is True

    def test_zero_std_different_current(self) -> None:
        """When all past values are identical but current differs."""
        history = [
            (datetime(2023, 6, 12, 10, 0), 5.0),
            (datetime(2024, 6, 10, 10, 0), 5.0),
            (datetime(2025, 6, 9, 10, 0), 10.0),
        ]
        assert detect_seasonality("changed", history) is False
