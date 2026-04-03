"""Structured error codes and response helpers. (RULE 12: all user-facing errors use error codes)"""

from __future__ import annotations

import asyncio
from enum import Enum

import structlog
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# Set by app startup to enable automatic error logging for 5xx responses.
_db_pool: object = None


def set_error_log_pool(pool: object) -> None:
    """Called at app startup to set the DB pool for error logging."""
    global _db_pool  # noqa: PLW0603
    _db_pool = pool


class ErrorCode(str, Enum):
    # --- Generic ---
    INTERNAL_ERROR = "E0001"
    VALIDATION_ERROR = "E0002"
    NOT_FOUND = "E0003"
    UNAUTHORIZED = "E0010"
    FORBIDDEN = "E0011"
    TOKEN_EXPIRED = "E0012"  # noqa: S105

    # --- Auth ---
    OAUTH_FAILED = "E0020"
    TWO_FA_REQUIRED = "E0021"

    # --- Quota / Plan ---
    QUOTA_EXCEEDED = "E0030"
    PLAN_GATE = "E0031"

    # --- DB / External ---
    DB_ERROR = "E0040"
    REDIS_ERROR = "E0041"
    EXTERNAL_API_ERROR = "E0050"

    # --- Resource ---
    DUPLICATE_ENTRY = "E0060"


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str | None = None


def error_response(
    code: ErrorCode,
    message: str,
    detail: str | None = None,
    status_code: int = 400,
) -> JSONResponse:
    body = ErrorResponse(code=code.value, message=message, detail=detail)

    # Auto-log server errors (5xx) to error_log table
    if status_code >= 500 and _db_pool is not None:
        try:
            from backend.common.error_log import write_error_log  # noqa: PLC0415

            asyncio.ensure_future(
                write_error_log(
                    _db_pool,
                    service="api",
                    message=message,
                    severity="error",
                    error_code=code.value,
                    detail={"detail": detail} if detail else None,
                )
            )
        except Exception:
            logger.warning("error_log_auto_write_skipped", code=code.value)

    return JSONResponse(status_code=status_code, content=body.model_dump())


def http_error(
    code: ErrorCode,
    message: str,
    status_code: int = 400,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code.value, "message": message},
    )
