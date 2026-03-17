"""Audit log writer. (RULE 06: try/except + structlog, RULE 07: type hints)"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


async def write_audit_log(
    conn: object,
    user_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    """Append an audit record to audit_log.

    Uses asyncpg parameterized queries (RULE 02).
    Fire-and-forget; errors are logged but not re-raised.
    """
    try:
        await conn.execute(  # type: ignore[attr-defined]
            """
            INSERT INTO audit_log
                (user_id, action, target_type, target_id, ip_address, user_agent, detail)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            user_id,
            action,
            target_type,
            target_id,
            ip_address,
            user_agent,
            detail,
        )
    except Exception as exc:
        logger.error(
            "audit_log_write_failed",
            user_id=user_id,
            action=action,
            error=str(exc),
        )
