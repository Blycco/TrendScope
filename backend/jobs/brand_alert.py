"""Scheduled job: brand crisis detection and alert dispatch.

Follows plan_expiry.py pattern.
RULE 02: asyncpg $1/$2 parameterization.
RULE 03: all I/O is async/await.
RULE 06: try/except + structlog logging.
RULE 07: type hints on all functions.
RULE 01: no hardcoded secrets — Slack webhook URL stored in DB only.
"""

from __future__ import annotations

import json

import asyncpg
import httpx
import structlog

from backend.processor.algorithms.brand_monitor import (
    _compute_stats,
    _fetch_alert_threshold,
    _fetch_recent_scores,
    calculate_zscore,
)
from backend.processor.shared.cache_manager import get_cached

logger = structlog.get_logger(__name__)


async def _send_slack_alert(webhook_url: str, message: str) -> None:
    """POST a plain-text alert to the given Slack webhook URL.

    Errors are logged but do not propagate so that one failed webhook
    never aborts the rest of the alert job.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                webhook_url,
                content=json.dumps({"text": message}),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
        logger.info("brand_slack_alert_sent", webhook_url=webhook_url[:30])
    except Exception as exc:
        logger.error("brand_slack_alert_failed", error=str(exc))


async def _log_email_alert(
    user_id: str,
    brand_name: str,
    z_score: float,
    label: str,
) -> None:
    """Log an email-alert event via structlog.

    Real SMTP delivery is handled by the notifications service; this job
    writes a structured log entry that can be picked up by that pipeline.

    RULE 01: no secrets logged.
    """
    logger.info(
        "brand_email_alert_triggered",
        user_id=user_id,
        brand_name=brand_name,
        z_score=round(z_score, 4),
        label=label,
        channel="email",
    )


async def run_brand_alert(pool: asyncpg.Pool) -> int:
    """Scan all active brand monitors and dispatch alerts for crisis events.

    For each active brand_monitor row:
    1. Fetch last 24h sentiment scores from sns_trend.
    2. Compute Z-score against the 24h baseline.
    3. If |Z-score| > alert_threshold: send Slack webhook + log email alert.
    4. Update last_alerted_at to suppress duplicate alerts within the same run.

    Returns the number of alerts dispatched.

    Args:
        pool: Active asyncpg connection pool.
    """
    try:
        async with pool.acquire() as conn:
            monitors = await conn.fetch(
                """
                SELECT id::text, user_id::text, brand_name, keywords,
                       slack_webhook, last_alerted_at
                FROM brand_monitor
                WHERE is_active = TRUE
                ORDER BY created_at ASC
                """
            )

        if not monitors:
            logger.info("brand_alert_job_no_monitors")
            return 0

        alert_threshold = await _fetch_alert_threshold(pool)
        alert_count = 0

        for row in monitors:
            brand_name: str = row["brand_name"]
            user_id: str = row["user_id"]
            keywords: list[str] = list(row["keywords"] or [])
            slack_webhook: str | None = row["slack_webhook"]

            try:
                # Skip if already alerted in the last 24h
                last_alerted_at = row["last_alerted_at"]
                if last_alerted_at is not None:
                    async with pool.acquire() as conn:
                        still_recent: bool = await conn.fetchval(
                            """
                            SELECT last_alerted_at > now() - INTERVAL '24 hours'
                            FROM brand_monitor
                            WHERE id = $1::uuid
                            """,
                            row["id"],
                        )
                    if still_recent:
                        logger.debug(
                            "brand_alert_suppressed_recent",
                            brand_name=brand_name,
                            user_id=user_id,
                        )
                        continue

                # Use cached result if available
                cache_key = f"brand:{user_id}:{brand_name.lower()}"
                cached_bytes = await get_cached(cache_key)
                z_score: float
                label: str
                is_crisis: bool

                if cached_bytes is not None:
                    try:
                        cached_data = json.loads(cached_bytes)
                        z_score = cached_data["z_score"]
                        label = cached_data["label"]
                        is_crisis = cached_data["is_crisis"]
                    except Exception:
                        cached_bytes = None

                if cached_bytes is None:
                    historical_scores = await _fetch_recent_scores(pool, brand_name, keywords)
                    mean_24h, std_24h = _compute_stats(historical_scores)
                    z_score = calculate_zscore(0.0, mean_24h, std_24h)
                    if std_24h == 0.0 and mean_24h < -0.3:
                        is_crisis = True
                        label = "crisis"
                    else:
                        is_crisis = abs(z_score) > alert_threshold
                        label = (
                            "crisis"
                            if (is_crisis and z_score < 0)
                            else "surge"
                            if (is_crisis and z_score > 0)
                            else "normal"
                        )

                if not is_crisis:
                    continue

                alert_message = (
                    f"[TrendScope] Brand Alert: *{brand_name}*\n"
                    f"Status: {label.upper()} | Z-score: {z_score:.2f} | "
                    f"Threshold: {alert_threshold}"
                )

                if slack_webhook:
                    await _send_slack_alert(slack_webhook, alert_message)

                await _log_email_alert(user_id, brand_name, z_score, label)

                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE brand_monitor
                        SET last_alerted_at = now(), updated_at = now()
                        WHERE id = $1::uuid
                        """,
                        row["id"],
                    )

                alert_count += 1
                logger.info(
                    "brand_alert_dispatched",
                    brand_name=brand_name,
                    user_id=user_id,
                    z_score=round(z_score, 4),
                    label=label,
                    slack=bool(slack_webhook),
                )

            except Exception as brand_exc:
                logger.error(
                    "brand_alert_row_failed",
                    brand_name=brand_name,
                    user_id=user_id,
                    error=str(brand_exc),
                )

        logger.info("brand_alert_job_complete", alert_count=alert_count)
        return alert_count

    except Exception as exc:
        logger.error("brand_alert_job_failed", error=str(exc))
        raise
