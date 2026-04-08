"""Prophet-based trend prediction for 72-hour horizon and 12-month forecasting.

Falls back to simple linear regression when Prophet is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_HORIZON_HOURS = 72
_DEFAULT_FORECAST_DAYS = 365


class TrendDirection(str, Enum):
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"


@dataclass
class PredictionResult:
    """Output of a trend prediction."""

    predicted_peak: float
    confidence: float
    trend_direction: TrendDirection
    horizon_hours: int = _DEFAULT_HORIZON_HOURS


@dataclass
class TimeSeriesPoint:
    """A single observation in the trend time series."""

    ds: datetime
    y: float


class TrendPredictor:
    """Predict trend trajectory using Prophet with linear fallback."""

    def __init__(self, horizon_hours: int = _DEFAULT_HORIZON_HOURS) -> None:
        self._horizon_hours = horizon_hours

    async def build_series(
        self,
        pool: object,
        group_id: str,
        *,
        days: int = 90,
    ) -> list[TimeSeriesPoint]:
        """Build daily mention-count time series for a trend group."""
        try:
            async with pool.acquire() as conn:  # type: ignore[union-attr]
                rows = await conn.fetch(
                    """
                    SELECT DATE(created_at) AS ds, COUNT(*) AS y
                    FROM news_article
                    WHERE group_id = $1::uuid
                      AND created_at > NOW() - make_interval(days => $2)
                    GROUP BY DATE(created_at)
                    ORDER BY ds
                    """,
                    group_id,
                    days,
                )
            return [
                TimeSeriesPoint(
                    ds=datetime.combine(row["ds"], datetime.min.time()).replace(
                        tzinfo=timezone.utc,
                    ),
                    y=float(row["y"]),
                )
                for row in rows
            ]
        except Exception as exc:
            logger.error("prediction_build_series_failed", group_id=group_id, error=str(exc))
            return []

    def predict(self, series: list[TimeSeriesPoint]) -> PredictionResult:
        """Predict future trend using Prophet, falling back to linear regression.

        Args:
            series: Historical daily observations (at least 3 points).

        Returns:
            PredictionResult with predicted peak, confidence, and direction.
        """
        if len(series) < 3:
            return PredictionResult(
                predicted_peak=series[-1].y if series else 0.0,
                confidence=0.0,
                trend_direction=TrendDirection.STABLE,
                horizon_hours=self._horizon_hours,
            )

        result = self._predict_prophet(series)
        if result is not None:
            return result

        return self._predict_linear(series)

    def _predict_prophet(self, series: list[TimeSeriesPoint]) -> PredictionResult | None:
        """Attempt Prophet forecast."""
        try:
            import pandas as pd
            from prophet import Prophet

            df = pd.DataFrame([{"ds": p.ds, "y": p.y} for p in series])
            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
            )
            model.fit(df)

            periods = max(1, self._horizon_hours // 24)
            future = model.make_future_dataframe(periods=periods)
            forecast = model.predict(future)

            future_rows = forecast.tail(periods)
            predicted_peak = float(future_rows["yhat"].max())
            last_actual = series[-1].y
            upper = float(future_rows["yhat_upper"].max())
            lower = float(future_rows["yhat_lower"].min())
            confidence = min(1.0, 1.0 / (1.0 + upper - lower))

            direction = self._determine_direction(last_actual, predicted_peak)

            logger.info(
                "prediction_prophet_success",
                peak=predicted_peak,
                confidence=confidence,
                direction=direction.value,
            )
            return PredictionResult(
                predicted_peak=predicted_peak,
                confidence=confidence,
                trend_direction=direction,
                horizon_hours=self._horizon_hours,
            )
        except Exception as exc:
            logger.warning("prediction_prophet_fallback", error=str(exc))
            return None

    def _predict_linear(self, series: list[TimeSeriesPoint]) -> PredictionResult:
        """Simple linear regression fallback."""
        ys = np.array([p.y for p in series])
        xs = np.arange(len(ys), dtype=np.float64)

        # Least squares: y = mx + b
        n = len(xs)
        sum_x = xs.sum()
        sum_y = ys.sum()
        sum_xy = (xs * ys).sum()
        sum_x2 = (xs**2).sum()

        denom = n * sum_x2 - sum_x**2
        if abs(denom) < 1e-10:
            return PredictionResult(
                predicted_peak=float(ys[-1]),
                confidence=0.1,
                trend_direction=TrendDirection.STABLE,
                horizon_hours=self._horizon_hours,
            )

        m = (n * sum_xy - sum_x * sum_y) / denom
        b = (sum_y - m * sum_x) / n

        future_steps = max(1, self._horizon_hours // 24)
        predicted_values = [m * (n + i) + b for i in range(future_steps)]
        predicted_peak = max(max(predicted_values), 0.0)

        direction = self._determine_direction(float(ys[-1]), predicted_peak)

        # Low confidence for linear model
        confidence = 0.3

        logger.info(
            "prediction_linear_success",
            peak=predicted_peak,
            slope=float(m),
            direction=direction.value,
        )
        return PredictionResult(
            predicted_peak=predicted_peak,
            confidence=confidence,
            trend_direction=direction,
            horizon_hours=self._horizon_hours,
        )

    @staticmethod
    def _determine_direction(current: float, predicted: float) -> TrendDirection:
        """Classify trend direction based on change ratio."""
        if current <= 0:
            return TrendDirection.RISING if predicted > 0 else TrendDirection.STABLE
        ratio = predicted / current
        if ratio > 1.1:
            return TrendDirection.RISING
        if ratio < 0.9:
            return TrendDirection.DECLINING
        return TrendDirection.STABLE


@dataclass
class ForecastPoint:
    """A single point in a forecast time series."""

    date: str
    yhat: float
    yhat_lower: float
    yhat_upper: float


async def forecast_trend(
    group_id: str,
    db_pool: object,
    horizon_days: int = _DEFAULT_FORECAST_DAYS,
) -> list[dict[str, object]]:
    """Generate a 12-month (or custom horizon) daily forecast for a trend group.

    Uses Prophet with yearly seasonality when available, otherwise falls back
    to simple linear extrapolation.

    Returns a list of dicts with keys: date, yhat, yhat_lower, yhat_upper.
    """
    try:
        predictor = TrendPredictor(horizon_hours=horizon_days * 24)
        series = await predictor.build_series(
            db_pool,
            group_id,
            days=max(180, horizon_days),
        )

        if len(series) < 3:
            logger.warning(
                "forecast_insufficient_data",
                group_id=group_id,
                points=len(series),
            )
            return []

        result = _forecast_prophet(series, horizon_days)
        if result is not None:
            return result

        return _forecast_linear(series, horizon_days)

    except Exception as exc:
        logger.error(
            "forecast_trend_failed",
            group_id=group_id,
            error=str(exc),
        )
        return []


def _forecast_prophet(
    series: list[TimeSeriesPoint],
    horizon_days: int,
) -> list[dict[str, object]] | None:
    """Attempt Prophet-based long-term forecast with yearly seasonality."""
    try:
        import pandas as pd
        from prophet import Prophet

        df = pd.DataFrame([{"ds": p.ds, "y": p.y} for p in series])
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
        )
        model.fit(df)

        future = model.make_future_dataframe(periods=horizon_days)
        forecast = model.predict(future)

        future_rows = forecast.tail(horizon_days)
        result: list[dict[str, object]] = []
        for _, row in future_rows.iterrows():
            result.append(
                {
                    "date": row["ds"].strftime("%Y-%m-%d"),
                    "yhat": round(max(0.0, float(row["yhat"])), 2),
                    "yhat_lower": round(max(0.0, float(row["yhat_lower"])), 2),
                    "yhat_upper": round(max(0.0, float(row["yhat_upper"])), 2),
                }
            )

        logger.info(
            "forecast_prophet_success",
            horizon_days=horizon_days,
            points=len(result),
        )
        return result

    except Exception as exc:
        logger.warning("forecast_prophet_fallback", error=str(exc))
        return None


def _forecast_linear(
    series: list[TimeSeriesPoint],
    horizon_days: int,
) -> list[dict[str, object]]:
    """Simple linear extrapolation fallback for long-term forecast."""
    ys = np.array([p.y for p in series])
    xs = np.arange(len(ys), dtype=np.float64)

    n = len(xs)
    sum_x = xs.sum()
    sum_y = ys.sum()
    sum_xy = (xs * ys).sum()
    sum_x2 = (xs**2).sum()

    denom = n * sum_x2 - sum_x**2
    if abs(denom) < 1e-10:
        m = 0.0
        b = float(ys.mean())
    else:
        m = float((n * sum_xy - sum_x * sum_y) / denom)
        b = float((sum_y - m * sum_x) / n)

    # Compute residual standard error for confidence band
    predictions = m * xs + b
    residuals = ys - predictions
    std_err = float(np.std(residuals)) if n > 2 else 0.0

    last_date = series[-1].ds
    result: list[dict[str, object]] = []

    for i in range(horizon_days):
        future_x = n + i
        yhat = max(0.0, m * future_x + b)
        margin = 1.96 * std_err * np.sqrt(1 + 1 / n + (future_x - xs.mean()) ** 2 / sum_x2)
        forecast_date = last_date + timedelta(days=i + 1)

        result.append(
            {
                "date": forecast_date.strftime("%Y-%m-%d"),
                "yhat": round(yhat, 2),
                "yhat_lower": round(max(0.0, yhat - margin), 2),
                "yhat_upper": round(max(0.0, yhat + margin), 2),
            }
        )

    logger.info(
        "forecast_linear_success",
        horizon_days=horizon_days,
        slope=m,
        points=len(result),
    )
    return result
