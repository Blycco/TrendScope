"""backend/common/quota_alert.py — Detect external API rate limits and record alerts."""

from __future__ import annotations

import asyncio

import asyncpg
import httpx
import structlog

logger = structlog.get_logger(__name__)

_DEBOUNCE_MINUTES = 10


def is_rate_limit_error(exc: Exception) -> tuple[bool, int | None, str | None]:
    """Check whether an exception represents a 429 / rate-limit error.

    Returns (is_rate_limit, status_code, detail_message).
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return True, 429, str(exc)

    try:
        from google.api_core.exceptions import ResourceExhausted  # type: ignore[import-untyped]

        if isinstance(exc, ResourceExhausted):
            return True, 429, str(exc)
    except ImportError:
        pass

    try:
        from openai import RateLimitError  # type: ignore[import-untyped]

        if isinstance(exc, RateLimitError):
            return True, 429, str(exc)
    except ImportError:
        pass

    return False, None, None


async def record_quota_alert(
    db_pool: asyncpg.Pool,
    service_name: str,
    error_type: str = "rate_limit_429",
    status_code: int | None = 429,
    detail: str | None = None,
    endpoint_url: str | None = None,
) -> None:
    """Insert an alert row and optionally send a debounced email."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO api_quota_alert
                    (service_name, error_type, status_code, detail, endpoint_url)
                VALUES ($1, $2, $3, $4, $5)
                """,
                service_name,
                error_type,
                status_code,
                detail[:1000] if detail else None,
                endpoint_url,
            )

            recent_count: int = await conn.fetchval(
                """
                SELECT count(*) FROM api_quota_alert
                WHERE service_name = $1
                  AND created_at > now() - interval '10 minutes'
                """,
                service_name,
            )

            should_email = recent_count <= 1

        if should_email:
            asyncio.create_task(_send_and_mark_email(db_pool, service_name, detail))

        logger.warning(
            "api_quota_alert_recorded",
            service_name=service_name,
            error_type=error_type,
            email_queued=should_email,
        )
    except Exception as exc:
        logger.error("quota_alert_record_failed", service_name=service_name, error=str(exc))


async def _send_and_mark_email(
    db_pool: asyncpg.Pool,
    service_name: str,
    detail: str | None,
) -> None:
    """Fire-and-forget: send email then mark the latest alert row."""
    try:
        from backend.common.email import send_quota_alert_email

        sent = await send_quota_alert_email(service_name, detail)
        if sent:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE api_quota_alert
                    SET email_sent = TRUE
                    WHERE id = (
                        SELECT id FROM api_quota_alert
                        WHERE service_name = $1
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                    """,
                    service_name,
                )
    except Exception as exc:
        logger.error("quota_alert_email_task_failed", error=str(exc))


async def handle_api_exception(
    exc: Exception,
    service_name: str,
    db_pool: asyncpg.Pool | None,
    endpoint_url: str | None = None,
) -> None:
    """One-liner helper: detect 429 and record alert if applicable."""
    if db_pool is None:
        return
    is_rl, status_code, detail = is_rate_limit_error(exc)
    if is_rl:
        await record_quota_alert(
            db_pool,
            service_name,
            "rate_limit_429",
            status_code,
            detail,
            endpoint_url,
        )
