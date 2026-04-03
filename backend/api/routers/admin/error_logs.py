"""Admin error log endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.errors import ErrorCode, http_error

router = APIRouter(prefix="/error-logs", tags=["admin-error-logs"])
logger = structlog.get_logger(__name__)


@router.get("")
async def list_error_logs(
    request: Request,
    service: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> dict:
    """Query error logs with optional filters."""
    try:
        pool = request.app.state.db_pool

        conditions: list[str] = []
        params: list[object] = []
        idx = 1

        if service:
            conditions.append(f"service = ${idx}")
            params.append(service)
            idx += 1
        if severity:
            conditions.append(f"severity = ${idx}")
            params.append(severity)
            idx += 1
        if date_from:
            conditions.append(f"occurred_at >= ${idx}")
            params.append(date_from)
            idx += 1
        if date_to:
            conditions.append(f"occurred_at <= ${idx}")
            params.append(date_to)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM error_log {where}"  # noqa: S608
        total = await pool.fetchval(count_query, *params)

        offset = (page - 1) * page_size
        data_query = (
            f"SELECT id, occurred_at, service, severity, error_code, "  # noqa: S608
            f"message, detail, user_id, request_path "
            f"FROM error_log {where} "
            f"ORDER BY occurred_at DESC "
            f"LIMIT ${idx} OFFSET ${idx + 1}"
        )
        params.extend([page_size, offset])

        rows = await pool.fetch(data_query, *params)

        items = [
            {
                "id": row["id"],
                "occurred_at": row["occurred_at"].isoformat() if row["occurred_at"] else None,
                "service": row["service"],
                "severity": row["severity"],
                "error_code": row["error_code"],
                "message": row["message"],
                "detail": row["detail"],
                "user_id": str(row["user_id"]) if row["user_id"] else None,
                "request_path": row["request_path"],
            }
            for row in rows
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_list_error_logs_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to list error logs", status_code=500) from exc
