"""Early trend score computation: burst + velocity + source diversity + recency."""

from __future__ import annotations

import json

import asyncpg
import structlog

from backend.processor.algorithms.burst import BurstResult
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_WEIGHTS_CACHE_TTL = 300  # 5 minutes
_DEFAULT_W_BURST = 0.3
_DEFAULT_W_VELOCITY = 0.3
_DEFAULT_W_DIVERSITY = 0.2
_DEFAULT_W_RECENCY = 0.2
_DEFAULT_ACCELERATION_DIVISOR = 5.0
_MIN_HOURLY_AVG = 0.1


async def _load_weights(pool: asyncpg.Pool) -> tuple[float, float, float, float]:
    """Load weights from admin_settings (Redis-cached, TTL 300s).

    Returns:
        Tuple of (w_burst, w_velocity, w_diversity, w_recency).
        Falls back to defaults on error.
    """
    cache_key = "early_trend_weights"
    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            w = json.loads(cached)
            return w["burst"], w["velocity"], w["diversity"], w.get("recency", _DEFAULT_W_RECENCY)
    except Exception as exc:
        logger.warning("early_trend_weights_cache_parse_failed", error=str(exc))

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT key, value FROM admin_settings WHERE key = ANY($1::text[])",
                [
                    "early_trend_w_burst",
                    "early_trend_w_velocity",
                    "early_trend_w_diversity",
                    "early_trend_w_recency",
                ],
            )
        kv = {r["key"]: float(r["value"].strip('"')) for r in rows}
    except Exception as exc:
        logger.warning("early_trend_weights_load_failed", error=str(exc))
        return _DEFAULT_W_BURST, _DEFAULT_W_VELOCITY, _DEFAULT_W_DIVERSITY, _DEFAULT_W_RECENCY

    burst = kv.get("early_trend_w_burst", _DEFAULT_W_BURST)
    velocity = kv.get("early_trend_w_velocity", _DEFAULT_W_VELOCITY)
    diversity = kv.get("early_trend_w_diversity", _DEFAULT_W_DIVERSITY)
    recency = kv.get("early_trend_w_recency", _DEFAULT_W_RECENCY)

    try:
        await set_cached(
            cache_key,
            json.dumps(
                {
                    "burst": burst,
                    "velocity": velocity,
                    "diversity": diversity,
                    "recency": recency,
                }
            ).encode(),
            _WEIGHTS_CACHE_TTL,
        )
    except Exception as exc:
        logger.warning("early_trend_weights_cache_set_failed", error=str(exc))

    return burst, velocity, diversity, recency


def compute_momentum_velocity(
    cnt_15m: int,
    cnt_1h: int,
    cnt_24h: int,
    acceleration_divisor: float = _DEFAULT_ACCELERATION_DIVISOR,
) -> float:
    """Compute momentum velocity with sub-hour granularity.

    Weights 15-minute activity 2x to detect rapid bursts sooner.

    Args:
        cnt_15m: Article count in last 15 minutes.
        cnt_1h:  Article count in last 1 hour.
        cnt_24h: Article count in last 24 hours.
        acceleration_divisor: Divisor for normalizing acceleration (default 5.0).

    Returns:
        Velocity in [0.0, 1.0].
    """
    weighted_recent = cnt_15m * 2.0 + (cnt_1h - cnt_15m)
    hourly_avg = cnt_24h / 24.0
    acceleration = weighted_recent / max(hourly_avg, _MIN_HOURLY_AVG)
    return min(1.0, acceleration / max(acceleration_divisor, 0.1))


async def compute_early_trend_score(
    pool: asyncpg.Pool,
    burst_result: BurstResult | float,
    velocity: float,
    source_diversity: float,
    recency: float = 0.0,
) -> float:
    """Compute early trend score from burst + velocity + diversity + recency.

    Weights loaded from admin_settings (Redis-cached, TTL 300s).
    Formula: w_burst*burst + w_velocity*velocity + w_diversity*diversity + w_recency*recency
    All inputs normalized to [0, 1], output clamped to [0, 1].

    Args:
        pool:             Active asyncpg connection pool.
        burst_result:     BurstResult from detect_burst(), or raw float score.
        velocity:         Rate of growth normalized to [0, 1].
        source_diversity: Source diversity score normalized to [0, 1].
        recency:          Recency score normalized to [0, 1].

    Returns:
        Early trend score in [0, 1].
    """
    burst_score = burst_result.score if isinstance(burst_result, BurstResult) else burst_result
    try:
        w_burst, w_velocity, w_diversity, w_recency = await _load_weights(pool)
        score = (
            w_burst * burst_score
            + w_velocity * velocity
            + w_diversity * source_diversity
            + w_recency * recency
        )
        return max(0.0, min(1.0, score))
    except Exception as exc:
        logger.warning("compute_early_trend_score_failed", error=str(exc))
        score = (
            _DEFAULT_W_BURST * burst_score
            + _DEFAULT_W_VELOCITY * velocity
            + _DEFAULT_W_DIVERSITY * source_diversity
            + _DEFAULT_W_RECENCY * recency
        )
        return max(0.0, min(1.0, score))
