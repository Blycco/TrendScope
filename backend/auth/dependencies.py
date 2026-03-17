"""FastAPI dependencies for authentication and plan-gate enforcement. (RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt import decode_token

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

PLAN_LEVEL: dict[str, int] = {
    "free": 0,
    "pro": 1,
    "business": 2,
    "enterprise": 3,
}


class CurrentUser:
    def __init__(self, user_id: str, plan: str, role: str) -> None:
        self.user_id = user_id
        self.plan = plan
        self.role = role


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> CurrentUser | None:
    """Return CurrentUser if a valid Bearer token is present, else None."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        return CurrentUser(
            user_id=payload["sub"],
            plan=payload.get("plan", "free"),
            role=payload.get("role", "general"),
        )
    except Exception as exc:
        logger.warning("jwt_decode_failed", error=str(exc))
        return None


async def require_auth(
    current_user: CurrentUser | None = Depends(get_current_user),  # noqa: B008
) -> CurrentUser:
    """Raise 401 if the request is not authenticated."""
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "E0010", "message": "Authentication required"},
        )
    return current_user


def require_plan(minimum_plan: str):  # noqa: ANN201
    """Dependency factory: raise 403 if user's plan is below minimum_plan."""

    async def _check(current_user: CurrentUser = Depends(require_auth)) -> CurrentUser:  # noqa: B008
        user_level = PLAN_LEVEL.get(current_user.plan, 0)
        required_level = PLAN_LEVEL.get(minimum_plan, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "E0031",
                    "message": "Plan upgrade required",
                    "required_plan": minimum_plan,
                    "current_plan": current_user.plan,
                    "upgrade_url": "/pricing",
                },
            )
        return current_user

    return _check
