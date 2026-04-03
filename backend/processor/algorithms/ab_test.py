"""A/B test routing for LTR vs rule-based ranking.

Uses deterministic hashing for consistent user→variant assignment.
"""

from __future__ import annotations

import hashlib

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_EXPERIMENT = "ltr_vs_rulebased"


class ABRouter:
    """Hash-based A/B test router with consistent assignment."""

    @staticmethod
    def assign_variant(user_id: str, experiment_name: str = _DEFAULT_EXPERIMENT) -> str:
        """Deterministically assign a user to a variant.

        Uses MD5 hash of ``user_id + experiment_name`` to ensure the same
        user always gets the same variant for a given experiment.

        Returns "control" or "treatment".
        """
        key = f"{user_id}:{experiment_name}"
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)  # noqa: S324
        return "treatment" if hash_val % 100 < 50 else "control"

    @staticmethod
    async def get_active_experiment(
        pool: object,
        name: str = _DEFAULT_EXPERIMENT,
    ) -> dict | None:
        """Fetch an active A/B experiment by name."""
        try:
            async with pool.acquire() as conn:  # type: ignore[union-attr]
                row = await conn.fetchrow(
                    """
                    SELECT id::text, name, description, variants, traffic_split,
                           is_active, started_at, ended_at
                    FROM ab_experiment
                    WHERE name = $1 AND is_active = TRUE
                    """,
                    name,
                )
            if row is None:
                return None
            return dict(row)
        except Exception as exc:
            logger.error("ab_get_experiment_failed", name=name, error=str(exc))
            return None

    @staticmethod
    async def log_exposure(
        pool: object,
        *,
        user_id: str,
        experiment_name: str,
        variant: str,
    ) -> None:
        """Record that a user was exposed to a variant.

        Uses ``user_action_log`` with action='ab_exposure'.
        """
        try:
            async with pool.acquire() as conn:  # type: ignore[union-attr]
                await conn.execute(
                    """
                    INSERT INTO user_action_log (user_id, action, meta)
                    VALUES ($1::uuid, 'ab_exposure',
                            $2::jsonb)
                    """,
                    user_id,
                    f'{{"experiment": "{experiment_name}", "variant": "{variant}"}}',
                )
        except Exception as exc:
            logger.warning("ab_log_exposure_failed", error=str(exc))


def should_use_ltr(user_id: str | None, experiment_active: bool = False) -> bool:
    """Determine whether to use LTR scoring for a given user.

    Args:
        user_id: Authenticated user ID. Anonymous users get rule-based.
        experiment_active: Whether the LTR A/B experiment is running.

    Returns:
        True if LTR should be used, False for rule-based.
    """
    if not experiment_active or user_id is None:
        return False
    variant = ABRouter.assign_variant(user_id)
    return variant == "treatment"
