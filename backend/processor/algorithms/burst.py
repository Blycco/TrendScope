"""Burst detection ensemble: Prophet + IsolationForest + CUSUM.

burst_score = 0.40*prophet + 0.35*iforest + 0.25*cusum
Levels: MEGA >0.90 / HIGH >0.75 / NORMAL >0.60 / END <0.30
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)

# --- Ensemble weights ---
_PROPHET_WEIGHT: float = 0.40
_IFOREST_WEIGHT: float = 0.35
_CUSUM_WEIGHT: float = 0.25


class BurstLevel(str, Enum):
    """Burst intensity level."""

    MEGA = "mega"  # >0.90
    HIGH = "high"  # >0.75
    NORMAL = "normal"  # >0.60
    LOW = "low"  # 0.30-0.60
    END = "end"  # <0.30


@dataclass
class BurstResult:
    """Burst detection result."""

    score: float
    level: BurstLevel
    prophet_score: float
    iforest_score: float
    cusum_score: float
    growth_type: str = "unknown"


@dataclass
class TimeSeriesPoint:
    """A single time series data point."""

    timestamp: float  # Unix timestamp
    value: float  # Frequency / mention count


def _classify_level(score: float) -> BurstLevel:
    """Classify burst score into level."""
    if score > 0.90:
        return BurstLevel.MEGA
    if score > 0.75:
        return BurstLevel.HIGH
    if score > 0.60:
        return BurstLevel.NORMAL
    if score >= 0.30:
        return BurstLevel.LOW
    return BurstLevel.END


def compute_prophet_score(series: list[TimeSeriesPoint]) -> float:
    """Compute Prophet-based anomaly score.

    Uses Prophet's yhat_upper * 1.5 threshold.
    Falls back to simple statistical detection if Prophet is unavailable.

    Args:
        series: Time series of frequency data.

    Returns:
        Anomaly score normalized to [0, 1].
    """
    if len(series) < 3:
        return 0.0

    values = [p.value for p in series]
    latest = values[-1]

    try:
        import pandas as pd  # type: ignore[import-untyped]
        from prophet import Prophet  # type: ignore[import-untyped]

        df = pd.DataFrame(
            {
                "ds": pd.to_datetime([p.timestamp for p in series], unit="s"),
                "y": values,
            }
        )

        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=True,
            suppress_stderr_logging=True,
        )
        model.fit(df)

        forecast = model.predict(df.tail(1))
        yhat_upper = forecast["yhat_upper"].iloc[0]
        threshold = yhat_upper * 1.5

        if threshold <= 0:
            return 0.0

        return min(1.0, max(0.0, latest / threshold))

    except ImportError:
        logger.debug("prophet_not_available", msg="using statistical fallback")
    except Exception as exc:
        logger.warning("prophet_failed", error=str(exc))

    # Fallback: z-score based detection
    return _statistical_anomaly_score(values)


def _statistical_anomaly_score(values: list[float]) -> float:
    """Simple z-score based anomaly detection as Prophet fallback."""
    if len(values) < 3:
        return 0.0

    latest = values[-1]
    history = values[:-1]
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std = variance**0.5

    if std == 0:
        return 1.0 if latest > mean else 0.0

    z = (latest - mean) / std
    # Normalize z-score to [0, 1] using sigmoid-like mapping
    return min(1.0, max(0.0, z / 6.0 + 0.5))


def compute_iforest_score(series: list[TimeSeriesPoint]) -> float:
    """Compute IsolationForest anomaly score.

    Uses contamination=0.01 as specified.
    Falls back to percentile-based detection if sklearn is unavailable.

    Args:
        series: Time series of frequency data.

    Returns:
        Anomaly score normalized to [0, 1].
    """
    if len(series) < 3:
        return 0.0

    values = [p.value for p in series]

    try:
        import numpy as np  # type: ignore[import-untyped]
        from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

        data = np.array(values).reshape(-1, 1)
        model = IsolationForest(contamination=0.01, random_state=42)
        model.fit(data)

        # score_samples returns negative anomaly scores
        scores = model.score_samples(data)
        latest_score = scores[-1]
        min_score = float(scores.min())
        max_score = float(scores.max())

        if max_score == min_score:
            return 0.5

        # Invert and normalize: more negative = more anomalous
        normalized = 1.0 - (latest_score - min_score) / (max_score - min_score)
        return min(1.0, max(0.0, normalized))

    except ImportError:
        logger.debug("sklearn_not_available", msg="using percentile fallback")
    except Exception as exc:
        logger.warning("iforest_failed", error=str(exc))

    # Fallback: percentile-based
    return _percentile_anomaly_score(values)


def _percentile_anomaly_score(values: list[float]) -> float:
    """Simple percentile-based anomaly detection as IForest fallback."""
    if len(values) < 3:
        return 0.0

    latest = values[-1]
    sorted_vals = sorted(values)
    rank = sum(1 for v in sorted_vals if v <= latest)
    percentile = rank / len(sorted_vals)
    # Map 99th+ percentile to high score
    return min(1.0, max(0.0, (percentile - 0.5) * 2))


def compute_cusum_score(series: list[TimeSeriesPoint]) -> float:
    """Compute CUSUM (Cumulative Sum) change-point score.

    CUSUM: max(0, prev + freq - mu - k), k = mu * 0.5

    Args:
        series: Time series of frequency data.

    Returns:
        Anomaly score normalized to [0, 1].
    """
    if len(series) < 3:
        return 0.0

    values = [p.value for p in series]
    mu = sum(values) / len(values)
    k = mu * 0.5  # Slack parameter

    # Compute CUSUM statistic
    cusum_pos = 0.0
    cusum_max = 0.0

    for val in values:
        cusum_pos = max(0.0, cusum_pos + val - mu - k)
        cusum_max = max(cusum_max, cusum_pos)

    # Normalize: use threshold = 5 * std as reference
    variance = sum((x - mu) ** 2 for x in values) / len(values)
    std = variance**0.5
    threshold = 5 * std if std > 0 else mu + 1

    if threshold <= 0:
        return 0.0

    return min(1.0, max(0.0, cusum_max / threshold))


def detect_burst(series: list[TimeSeriesPoint]) -> BurstResult:
    """Run the burst detection ensemble.

    Combines Prophet, IsolationForest, and CUSUM scores.
    burst_score = 0.40*prophet + 0.35*iforest + 0.25*cusum

    Args:
        series: Time series of frequency data (at least 3 points).

    Returns:
        BurstResult with ensemble score and level.
    """
    if len(series) < 3:
        return BurstResult(
            score=0.0,
            level=BurstLevel.END,
            prophet_score=0.0,
            iforest_score=0.0,
            cusum_score=0.0,
        )

    prophet_score = compute_prophet_score(series)
    iforest_score = compute_iforest_score(series)
    cusum_score = compute_cusum_score(series)

    ensemble_score = (
        _PROPHET_WEIGHT * prophet_score
        + _IFOREST_WEIGHT * iforest_score
        + _CUSUM_WEIGHT * cusum_score
    )

    level = _classify_level(ensemble_score)

    logger.info(
        "burst_detected",
        score=round(ensemble_score, 4),
        level=level.value,
        prophet=round(prophet_score, 4),
        iforest=round(iforest_score, 4),
        cusum=round(cusum_score, 4),
    )

    return BurstResult(
        score=ensemble_score,
        level=level,
        prophet_score=prophet_score,
        iforest_score=iforest_score,
        cusum_score=cusum_score,
    )
