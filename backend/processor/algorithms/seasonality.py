"""Seasonality detection — flag recurring keyword bursts using rolling statistics.

Uses rolling mean + standard deviation instead of Prophet to stay lightweight.
A keyword is seasonal if it appeared with similar frequency at roughly the same
calendar period in past data (within a configurable tolerance window).
"""

from __future__ import annotations

from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)

# A keyword is seasonal when at least this many past windows show similar activity
_MIN_RECURRING_WINDOWS: int = 2
# Tolerance: past value within mean +/- 1 std is considered "similar"
_SIMILARITY_THRESHOLD_SIGMA: float = 1.0
# Window size in days for grouping history into calendar periods
_WINDOW_DAYS: int = 7


def detect_seasonality(
    keyword: str,
    history: list[tuple[datetime, float]],
) -> bool:
    """Detect whether a keyword's burst pattern is seasonal/recurring.

    Groups historical data into weekly windows aligned to the same week-of-year,
    computes a rolling mean and standard deviation, and checks whether recent
    activity falls within the expected range seen in prior years/periods.

    Args:
        keyword: The keyword being evaluated.
        history: List of (datetime, frequency_value) tuples sorted by time.

    Returns:
        True if the keyword shows seasonal/recurring patterns.
    """
    if len(history) < _MIN_RECURRING_WINDOWS + 1:
        logger.debug("seasonality_insufficient_data", keyword=keyword, points=len(history))
        return False

    # Group values by week-of-year
    week_buckets: dict[int, list[float]] = {}
    for dt, value in history:
        week_num = dt.isocalendar()[1]
        week_buckets.setdefault(week_num, []).append(value)

    # Find the current week (last entry in history)
    current_week = history[-1][0].isocalendar()[1]
    current_value = history[-1][1]

    past_values = week_buckets.get(current_week, [])

    # Exclude the current value itself if present
    if past_values and past_values[-1] == current_value:
        past_values = past_values[:-1]

    if len(past_values) < _MIN_RECURRING_WINDOWS:
        logger.debug(
            "seasonality_not_enough_recurring",
            keyword=keyword,
            week=current_week,
            past_count=len(past_values),
        )
        return False

    mean = sum(past_values) / len(past_values)
    variance = sum((v - mean) ** 2 for v in past_values) / len(past_values)
    std = variance**0.5

    lower = mean - _SIMILARITY_THRESHOLD_SIGMA * std
    upper = mean + _SIMILARITY_THRESHOLD_SIGMA * std

    is_seasonal = lower <= current_value <= upper

    logger.info(
        "seasonality_check",
        keyword=keyword,
        is_seasonal=is_seasonal,
        current_value=current_value,
        mean=round(mean, 4),
        std=round(std, 4),
        week=current_week,
        past_count=len(past_values),
    )
    return is_seasonal
