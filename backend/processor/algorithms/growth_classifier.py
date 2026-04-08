"""Growth vs Spike 분류기. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class GrowthType(str, Enum):
    GROWTH = "growth"
    SPIKE = "spike"
    UNKNOWN = "unknown"


@dataclass
class VelocityWindow:
    window_start_hours_ago: int  # 예: 0
    window_end_hours_ago: int  # 예: 12
    article_count: int


def classify_growth_type(windows: list[VelocityWindow]) -> GrowthType:
    """Growth vs Spike 분류.

    windows: 최신→과거 순 12h 단위 목록 [0-12h, 12-24h, 24-36h, ...]

    spike: recent >= 3 * mid AND mid <= 2  (단기 폭발, 이전은 낮음)
    growth: recent >= mid * 1.2 AND (창 2개 이상 있으면) mid >= old * 1.1
    otherwise: UNKNOWN

    Args:
        windows: 최신→과거 순으로 정렬된 VelocityWindow 목록.

    Returns:
        GrowthType 분류 결과.
    """
    try:
        if len(windows) < 2:
            return GrowthType.UNKNOWN

        recent = windows[0].article_count
        mid = windows[1].article_count

        # spike 판단
        if mid <= 2 and recent >= 3 * max(mid, 1):
            logger.info(
                "growth_type_classified",
                growth_type=GrowthType.SPIKE.value,
                recent=recent,
                mid=mid,
            )
            return GrowthType.SPIKE

        # growth 판단 (3창 필요)
        if len(windows) >= 3:
            old = windows[2].article_count
            if recent >= mid * 1.2 and mid >= old * 1.1:
                logger.info(
                    "growth_type_classified",
                    growth_type=GrowthType.GROWTH.value,
                    recent=recent,
                    mid=mid,
                    old=old,
                )
                return GrowthType.GROWTH
        elif recent >= mid * 1.5:
            # 2창만 있어도 확실한 상승이면 growth
            logger.info(
                "growth_type_classified",
                growth_type=GrowthType.GROWTH.value,
                recent=recent,
                mid=mid,
            )
            return GrowthType.GROWTH

        logger.info(
            "growth_type_classified",
            growth_type=GrowthType.UNKNOWN.value,
            recent=recent,
            mid=mid,
        )
        return GrowthType.UNKNOWN

    except Exception as exc:
        logger.warning("growth_type_classification_failed", error=str(exc))
        return GrowthType.UNKNOWN
