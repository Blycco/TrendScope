"""Early trend score computation: burst + velocity + source diversity. (RULE 07: type hints)"""

from __future__ import annotations

import json

import asyncpg
import structlog

from backend.processor.algorithms.burst import BurstResult
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_WEIGHTS_CACHE_TTL = 300  # 5 minutes


async def _load_weights(pool: asyncpg.Pool) -> tuple[float, float, float]:
    """Load weights from admin_settings (Redis-cached, TTL 300s).

    Returns:
        Tuple of (w_burst, w_velocity, w_diversity). Falls back to defaults on error.
    """
    cache_key = "early_trend_weights"
    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            w = json.loads(cached)
            return w["burst"], w["velocity"], w["diversity"]
    except Exception as exc:
        logger.warning("early_trend_weights_cache_parse_failed", error=str(exc))

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT key, value FROM admin_settings WHERE key = ANY($1::text[])",
                ["early_trend_w_burst", "early_trend_w_velocity", "early_trend_w_diversity"],
            )
        kv = {r["key"]: float(r["value"].strip('"')) for r in rows}
    except Exception as exc:
        logger.warning("early_trend_weights_load_failed", error=str(exc))
        return 0.5, 0.3, 0.2

    burst = kv.get("early_trend_w_burst", 0.5)
    velocity = kv.get("early_trend_w_velocity", 0.3)
    diversity = kv.get("early_trend_w_diversity", 0.2)

    try:
        await set_cached(
            cache_key,
            json.dumps({"burst": burst, "velocity": velocity, "diversity": diversity}).encode(),
            _WEIGHTS_CACHE_TTL,
        )
    except Exception as exc:
        logger.warning("early_trend_weights_cache_set_failed", error=str(exc))

    return burst, velocity, diversity


async def compute_early_trend_score(
    pool: asyncpg.Pool,
    burst_result: BurstResult,
    velocity: float,
    source_diversity: float,
) -> float:
    """Compute early trend score from burst detection result.

    Weights loaded from admin_settings (Redis-cached, TTL 300s).
    Formula: w_burst * burst_score + w_velocity * velocity + w_diversity * source_diversity
    All inputs normalized to [0, 1], output clamped to [0, 1].

    Args:
        pool:             Active asyncpg connection pool.
        burst_result:     BurstResult from detect_burst().
        velocity:         Rate of growth normalized to [0, 1].
        source_diversity: Source diversity score normalized to [0, 1].

    Returns:
        Early trend score in [0, 1].
    """
    try:
        w_burst, w_velocity, w_diversity = await _load_weights(pool)
        score = (
            w_burst * burst_result.score + w_velocity * velocity + w_diversity * source_diversity
        )
        return max(0.0, min(1.0, score))
    except Exception as exc:
        logger.warning("compute_early_trend_score_failed", error=str(exc))
        # Fallback with default weights
        score = 0.5 * burst_result.score + 0.3 * velocity + 0.2 * source_diversity
        return max(0.0, min(1.0, score))
