"""Error log writer. Append-only, fire-and-forget. (RULE 06, RULE 07)"""

from __future__ import annotations

import json

import structlog

logger = structlog.get_logger(__name__)


async def write_error_log(
    pool: object,
    service: str,
    message: str,
    *,
    severity: str = "error",
    error_code: str | None = None,
    detail: dict | None = None,
    user_id: str | None = None,
    request_path: str | None = None,
) -> None:
    """Append an error record to error_log table.

    Fire-and-forget; errors are logged via structlog but never re-raised.
    """
    try:
        detail_json = json.dumps(detail, ensure_ascii=False, default=str) if detail else None
        async with pool.acquire() as conn:  # type: ignore[attr-defined]
            await conn.execute(
                """
                INSERT INTO error_log
                    (service, severity, error_code, message, detail, user_id, request_path)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::uuid, $7)
                """,
                service,
                severity,
                error_code,
                message,
                detail_json,
                user_id,
                request_path,
            )
    except Exception as exc:
        logger.error(
            "error_log_write_failed",
            service=service,
            message=message,
            error=str(exc),
        )
