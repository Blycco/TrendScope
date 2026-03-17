"""Structured error codes and response helpers. (RULE 12: all user-facing errors use error codes)"""

from enum import Enum

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, Enum):
    # --- Generic ---
    INTERNAL_ERROR = "E0001"
    VALIDATION_ERROR = "E0002"
    NOT_FOUND = "E0003"
    UNAUTHORIZED = "E0010"
    FORBIDDEN = "E0011"
    TOKEN_EXPIRED = "E0012"

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
