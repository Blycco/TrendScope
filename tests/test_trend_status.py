"""Tests for trend status classification."""

from __future__ import annotations

from backend.processor.algorithms.trend_status import classify_trend_status


class TestExploding:
    """Exploding status: score increase > 50% or score > 80 with direction up."""

    def test_large_increase(self) -> None:
        assert classify_trend_status(90.0, 50.0, "steady") == "exploding"

    def test_high_score_with_up_direction(self) -> None:
        assert classify_trend_status(85.0, None, "up") == "exploding"

    def test_high_score_with_rising_direction(self) -> None:
        assert classify_trend_status(85.0, None, "rising") == "exploding"

    def test_just_above_threshold(self) -> None:
        # 51% increase
        assert classify_trend_status(75.5, 50.0, "steady") == "exploding"


class TestRising:
    """Rising status: score increase > 10% or direction up."""

    def test_moderate_increase(self) -> None:
        assert classify_trend_status(56.0, 50.0, "steady") == "rising"

    def test_direction_up_low_score(self) -> None:
        assert classify_trend_status(30.0, None, "up") == "rising"

    def test_direction_rising(self) -> None:
        assert classify_trend_status(30.0, None, "rising") == "rising"


class TestPeaked:
    """Peaked status: score decrease < 10% but score > 60."""

    def test_small_decline_high_score(self) -> None:
        assert classify_trend_status(65.0, 70.0, "down") == "peaked"

    def test_small_decline_no_direction(self) -> None:
        # -5% decline, score > 60, negative change
        assert classify_trend_status(66.5, 70.0, "steady") == "peaked"


class TestDeclining:
    """Declining status: score decrease > 10% or direction down."""

    def test_large_decrease(self) -> None:
        assert classify_trend_status(40.0, 50.0, "steady") == "declining"

    def test_direction_down(self) -> None:
        assert classify_trend_status(30.0, None, "down") == "declining"

    def test_direction_declining(self) -> None:
        assert classify_trend_status(30.0, None, "declining") == "declining"


class TestStable:
    """Stable status: everything else."""

    def test_no_change(self) -> None:
        assert classify_trend_status(50.0, 50.0, "steady") == "stable"

    def test_no_prev_score_steady(self) -> None:
        assert classify_trend_status(50.0, None, "steady") == "stable"

    def test_no_prev_score_no_direction(self) -> None:
        assert classify_trend_status(50.0, None, None) == "stable"

    def test_zero_prev_score(self) -> None:
        assert classify_trend_status(50.0, 0.0, "steady") == "stable"


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_zero_scores(self) -> None:
        assert classify_trend_status(0.0, 0.0, None) == "stable"

    def test_negative_score(self) -> None:
        # Should not crash
        result = classify_trend_status(-5.0, 10.0, None)
        assert result in ("exploding", "rising", "stable", "declining", "peaked")

    def test_prev_score_none_direction_none(self) -> None:
        assert classify_trend_status(50.0, None, None) == "stable"
