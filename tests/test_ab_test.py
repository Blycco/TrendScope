"""Tests for A/B test routing module."""

from __future__ import annotations

from backend.processor.algorithms.ab_test import ABRouter, should_use_ltr


class TestABRouter:
    def test_assign_variant_deterministic(self) -> None:
        """Same user + experiment always gets same variant."""
        v1 = ABRouter.assign_variant("user-123", "exp1")
        v2 = ABRouter.assign_variant("user-123", "exp1")
        assert v1 == v2

    def test_assign_variant_returns_valid_values(self) -> None:
        variants = {ABRouter.assign_variant(f"user-{i}") for i in range(200)}
        assert variants == {"control", "treatment"}

    def test_assign_variant_different_experiments(self) -> None:
        """Different experiments can yield different variants for same user."""
        results = {ABRouter.assign_variant("user-42", f"exp-{i}") for i in range(50)}
        # With 50 different experiments, we should see both variants
        assert len(results) == 2

    def test_assign_variant_roughly_even_split(self) -> None:
        """~50/50 split across many users."""
        variants = [ABRouter.assign_variant(f"u-{i}") for i in range(1000)]
        treatment_pct = variants.count("treatment") / len(variants)
        assert 0.4 < treatment_pct < 0.6


class TestShouldUseLtr:
    def test_no_experiment_returns_false(self) -> None:
        assert should_use_ltr("user-1", experiment_active=False) is False

    def test_anonymous_user_returns_false(self) -> None:
        assert should_use_ltr(None, experiment_active=True) is False

    def test_active_experiment_returns_bool(self) -> None:
        result = should_use_ltr("user-1", experiment_active=True)
        assert isinstance(result, bool)

    def test_consistent_assignment(self) -> None:
        """Same user always gets same LTR decision."""
        r1 = should_use_ltr("user-99", experiment_active=True)
        r2 = should_use_ltr("user-99", experiment_active=True)
        assert r1 == r2
