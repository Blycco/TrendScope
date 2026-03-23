"""Admin audit log endpoints. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from backend.api.schemas.admin import AdminAuditItem, AdminAuditListResponse
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.admin import admin_list_audit_logs

router = APIRouter(prefix="/audit", tags=["admin-audit"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=AdminAuditListResponse)
async def list_audit_logs(
    request: Request,
    user_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> AdminAuditListResponse:
    """Query audit logs with optional filters."""
    try:
        pool = request.app.state.db_pool
        rows, total = await admin_list_audit_logs(
            pool,
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        items = [
            AdminAuditItem(
                id=row["id"],
                user_id=row["user_id"],
                action=row["action"],
                target_type=row["target_type"],
                target_id=row["target_id"],
                ip_address=row["ip_address"],
                detail=row["detail"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return AdminAuditListResponse(logs=items, total=total, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_list_audit_logs_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to list audit logs", status_code=500) from exc


@router.get("/export")
async def export_audit_logs(
    request: Request,
    format: str = "json",
    user_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> Response:
    """Export audit logs as JSON or CSV."""
    try:
        pool = request.app.state.db_pool
        rows, _ = await admin_list_audit_logs(
            pool,
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            page=1,
            page_size=10000,
        )

        items = [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "action": row["action"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "ip_address": row["ip_address"],
                "detail": row["detail"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

        if format == "csv":
            output = io.StringIO()
            fieldnames = [
                "id",
                "user_id",
                "action",
                "target_type",
                "target_id",
                "ip_address",
                "detail",
                "created_at",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                item["detail"] = json.dumps(item["detail"]) if item["detail"] else ""
                writer.writerow(item)
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
            )

        return Response(
            content=json.dumps(items, default=str),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_log.json"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_export_audit_logs_failed", error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR, "Failed to export audit logs", status_code=500
        ) from exc
