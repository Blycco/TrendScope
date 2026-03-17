"""Tests for common/errors.py."""

from __future__ import annotations

from backend.common.errors import ErrorCode, ErrorResponse, error_response, http_error
from fastapi.responses import JSONResponse


def test_error_code_values() -> None:
    assert ErrorCode.INTERNAL_ERROR == "E0001"
    assert ErrorCode.VALIDATION_ERROR == "E0002"
    assert ErrorCode.NOT_FOUND == "E0003"
    assert ErrorCode.UNAUTHORIZED == "E0010"
    assert ErrorCode.QUOTA_EXCEEDED == "E0030"
    assert ErrorCode.DB_ERROR == "E0040"
    assert ErrorCode.REDIS_ERROR == "E0041"


def test_error_response_model() -> None:
    resp = ErrorResponse(code="E0001", message="test error")
    assert resp.code == "E0001"
    assert resp.message == "test error"
    assert resp.detail is None


def test_error_response_with_detail() -> None:
    resp = ErrorResponse(code="E0001", message="test", detail="extra info")
    assert resp.detail == "extra info"


def test_error_response_helper_default_status() -> None:
    result = error_response(ErrorCode.INTERNAL_ERROR, "something went wrong")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400


def test_error_response_helper_custom_status() -> None:
    result = error_response(ErrorCode.UNAUTHORIZED, "not authorized", status_code=401)
    assert result.status_code == 401


def test_error_response_helper_with_detail() -> None:
    result = error_response(
        ErrorCode.VALIDATION_ERROR, "invalid input", detail="field x is required"
    )
    assert result.status_code == 400


def test_http_error_default_status() -> None:
    exc = http_error(ErrorCode.NOT_FOUND, "resource not found")
    assert exc.status_code == 400
    assert exc.detail["code"] == "E0003"
    assert exc.detail["message"] == "resource not found"


def test_http_error_custom_status() -> None:
    exc = http_error(ErrorCode.FORBIDDEN, "forbidden", status_code=403)
    assert exc.status_code == 403
