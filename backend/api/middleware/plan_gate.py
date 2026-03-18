"""Plan gate middleware — server-side plan enforcement. (RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.auth.dependencies import PLAN_LEVEL
from backend.auth.jwt import decode_token
from backend.common.errors import ErrorCode

logger = structlog.get_logger(__name__)

# path prefix → minimum plan required
PLAN_GATES: dict[str, str] = {
    "/api/v1/trends/early": "pro",
    "/api/v1/content/ideas": "pro",
    "/api/v1/brand/": "business",
}

# paths matched by suffix segment — checked separately
_INSIGHT_SUFFIX = "/insights"


def _extract_user_plan(request: Request) -> str | None:
    """Extract plan from Bearer JWT, or None if unauthenticated/invalid."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer ") :]
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("plan", "free")
    except Exception:
        return None


def _required_plan(path: str) -> str | None:
    """Return the minimum plan required for *path*, or None if ungated."""
    # exact prefix matches
    for prefix, plan in PLAN_GATES.items():
        if path.startswith(prefix):
            return plan
    # /api/v1/trends/{kw}/insights
    if path.startswith("/api/v1/trends/") and path.endswith(_INSIGHT_SUFFIX):
        return "pro"
    return None


class PlanGateMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001, ANN201
        try:
            required = _required_plan(request.url.path)
            if required is None:
                return await call_next(request)

            user_plan = _extract_user_plan(request)
            if user_plan is None:
                logger.info(
                    "plan_gate_unauthenticated",
                    path=request.url.path,
                    required=required,
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "code": ErrorCode.UNAUTHORIZED.value,
                        "message": "Authentication required",
                        "message_key": "error.unauthorized",
                    },
                )

            user_level = PLAN_LEVEL.get(user_plan, 0)
            required_level = PLAN_LEVEL.get(required, 0)
            if user_level < required_level:
                logger.info(
                    "plan_gate_denied",
                    path=request.url.path,
                    user_plan=user_plan,
                    required=required,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": ErrorCode.PLAN_GATE.value,
                        "message": "Plan upgrade required",
                        "message_key": "error.plan_gate",
                        "required_plan": required,
                        "current_plan": user_plan,
                        "upgrade_url": "/pricing",
                    },
                )

            return await call_next(request)
        except Exception as exc:
            logger.error("plan_gate_middleware_error", error=str(exc), path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "Internal server error",
                    "message_key": "error.internal",
                },
            )
