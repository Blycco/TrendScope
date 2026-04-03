"""ALS-style Collaborative Filtering using TruncatedSVD.

Builds a user–group interaction matrix from ``user_action_log`` and produces
per-user recommendations.  Returns 0.0 gracefully when data is insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Implicit signal weights
_SIGNAL_WEIGHTS: dict[str, float] = {
    "click": 1.0,
    "scrap": 3.0,
    "dwell": 2.0,
}

_MIN_INTERACTIONS = 5
_DEFAULT_N_COMPONENTS = 20


@dataclass
class CFResult:
    """A single recommendation entry."""

    group_id: str
    score: float


class CollaborativeFilter:
    """User-based collaborative filter backed by TruncatedSVD."""

    def __init__(self, n_components: int = _DEFAULT_N_COMPONENTS) -> None:
        self._n_components = n_components
        self._user_factors: np.ndarray | None = None
        self._item_factors: np.ndarray | None = None
        self._user_index: dict[str, int] = {}
        self._item_index: dict[str, int] = {}
        self._item_ids: list[str] = []

    @property
    def is_fitted(self) -> bool:
        return self._user_factors is not None

    # ------------------------------------------------------------------
    # Build interaction matrix
    # ------------------------------------------------------------------

    async def build_interaction_matrix(
        self,
        pool: object,
        *,
        days: int = 30,
    ) -> np.ndarray | None:
        """Query ``user_action_log`` and build a user×group matrix.

        Returns the dense matrix or ``None`` if data is insufficient.
        """
        try:
            async with pool.acquire() as conn:  # type: ignore[union-attr]
                rows = await conn.fetch(
                    """
                    SELECT
                        user_id::text,
                        item_id::text AS group_id,
                        action,
                        COUNT(*) AS cnt,
                        AVG(dwell_ms) FILTER (WHERE dwell_ms > 0) AS avg_dwell
                    FROM user_action_log
                    WHERE item_type = 'trend'
                      AND created_at > NOW() - make_interval(days => $1)
                    GROUP BY user_id, item_id, action
                    """,
                    days,
                )
        except Exception as exc:
            logger.error("cf_build_matrix_failed", error=str(exc))
            return None

        if len(rows) < _MIN_INTERACTIONS:
            logger.info("cf_insufficient_data", row_count=len(rows))
            return None

        # Build indices
        users: dict[str, int] = {}
        items: dict[str, int] = {}
        for row in rows:
            uid = row["user_id"]
            gid = row["group_id"]
            if uid not in users:
                users[uid] = len(users)
            if gid not in items:
                items[gid] = len(items)

        matrix = np.zeros((len(users), len(items)), dtype=np.float32)
        for row in rows:
            u = users[row["user_id"]]
            i = items[row["group_id"]]
            weight = _SIGNAL_WEIGHTS.get(row["action"], 1.0)
            cnt = row["cnt"]
            # Dwell bonus: >10s counts as implicit positive
            dwell_bonus = 1.0 if (row["avg_dwell"] or 0) > 10000 else 0.0
            matrix[u, i] += weight * cnt + dwell_bonus

        self._user_index = users
        self._item_index = items
        self._item_ids = [""] * len(items)
        for gid, idx in items.items():
            self._item_ids[idx] = gid

        logger.info("cf_matrix_built", users=len(users), items=len(items), interactions=len(rows))
        return matrix

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, matrix: np.ndarray) -> None:
        """Fit TruncatedSVD on the interaction matrix."""
        try:
            from sklearn.decomposition import TruncatedSVD

            n_comp = min(self._n_components, min(matrix.shape) - 1)
            if n_comp < 1:
                logger.warning("cf_matrix_too_small")
                return

            svd = TruncatedSVD(n_components=n_comp, random_state=42)
            self._user_factors = svd.fit_transform(matrix)
            self._item_factors = svd.components_.T
            logger.info("cf_model_fitted", n_components=n_comp)
        except Exception as exc:
            logger.error("cf_fit_failed", error=str(exc))
            self._user_factors = None
            self._item_factors = None

    # ------------------------------------------------------------------
    # Recommend
    # ------------------------------------------------------------------

    def recommend(self, user_id: str, top_k: int = 20) -> list[CFResult]:
        """Return top-K recommendations for a user."""
        if not self.is_fitted or user_id not in self._user_index:
            return []

        u_idx = self._user_index[user_id]
        scores = self._user_factors[u_idx] @ self._item_factors.T  # type: ignore[index]
        top_indices = np.argsort(scores)[::-1][:top_k]

        return [
            CFResult(group_id=self._item_ids[i], score=float(scores[i]))
            for i in top_indices
            if scores[i] > 0
        ]

    def get_cf_score(self, user_id: str, group_id: str) -> float:
        """Get CF affinity score for a specific user–group pair.

        Returns 0.0 if model is not fitted or user/group unknown.
        Used as a feature in the LTR ranking model.
        """
        if not self.is_fitted:
            return 0.0
        if user_id not in self._user_index or group_id not in self._item_index:
            return 0.0

        u_idx = self._user_index[user_id]
        i_idx = self._item_index[group_id]
        score = float(self._user_factors[u_idx] @ self._item_factors[i_idx])  # type: ignore[index]
        return max(0.0, score)
