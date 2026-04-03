"""Tests for collaborative filtering module."""

from __future__ import annotations

import numpy as np
from backend.processor.algorithms.cf import CFResult, CollaborativeFilter


class TestCollaborativeFilter:
    def test_not_fitted_initially(self) -> None:
        cf = CollaborativeFilter()
        assert not cf.is_fitted

    def test_fit_on_small_matrix(self) -> None:
        cf = CollaborativeFilter(n_components=2)
        matrix = np.array(
            [
                [5.0, 0.0, 3.0, 0.0],
                [0.0, 4.0, 0.0, 2.0],
                [3.0, 0.0, 5.0, 0.0],
            ],
            dtype=np.float32,
        )
        cf._user_index = {"u1": 0, "u2": 1, "u3": 2}
        cf._item_index = {"g1": 0, "g2": 1, "g3": 2, "g4": 3}
        cf._item_ids = ["g1", "g2", "g3", "g4"]
        cf.fit(matrix)

        assert cf.is_fitted

    def test_recommend_returns_results(self) -> None:
        cf = CollaborativeFilter(n_components=2)
        matrix = np.array(
            [
                [5.0, 0.0, 3.0],
                [0.0, 4.0, 0.0],
                [3.0, 0.0, 5.0],
            ],
            dtype=np.float32,
        )
        cf._user_index = {"u1": 0, "u2": 1, "u3": 2}
        cf._item_index = {"g1": 0, "g2": 1, "g3": 2}
        cf._item_ids = ["g1", "g2", "g3"]
        cf.fit(matrix)

        results = cf.recommend("u1", top_k=3)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, CFResult)
            assert r.group_id in ["g1", "g2", "g3"]

    def test_recommend_unknown_user_returns_empty(self) -> None:
        cf = CollaborativeFilter(n_components=2)
        matrix = np.array([[5.0, 3.0], [3.0, 5.0]], dtype=np.float32)
        cf._user_index = {"u1": 0, "u2": 1}
        cf._item_index = {"g1": 0, "g2": 1}
        cf._item_ids = ["g1", "g2"]
        cf.fit(matrix)

        results = cf.recommend("unknown_user")
        assert results == []

    def test_get_cf_score_not_fitted(self) -> None:
        cf = CollaborativeFilter()
        assert cf.get_cf_score("u1", "g1") == 0.0

    def test_get_cf_score_unknown_pair(self) -> None:
        cf = CollaborativeFilter(n_components=2)
        matrix = np.array([[5.0, 3.0], [3.0, 5.0]], dtype=np.float32)
        cf._user_index = {"u1": 0, "u2": 1}
        cf._item_index = {"g1": 0, "g2": 1}
        cf._item_ids = ["g1", "g2"]
        cf.fit(matrix)

        assert cf.get_cf_score("u1", "unknown_group") == 0.0
        assert cf.get_cf_score("unknown_user", "g1") == 0.0

    def test_get_cf_score_known_pair(self) -> None:
        cf = CollaborativeFilter(n_components=2)
        matrix = np.array(
            [
                [5.0, 0.0],
                [0.0, 5.0],
            ],
            dtype=np.float32,
        )
        cf._user_index = {"u1": 0, "u2": 1}
        cf._item_index = {"g1": 0, "g2": 1}
        cf._item_ids = ["g1", "g2"]
        cf.fit(matrix)

        score = cf.get_cf_score("u1", "g1")
        assert score >= 0.0
