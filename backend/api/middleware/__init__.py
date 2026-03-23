"""API middleware package: Starlette middleware classes + FastAPI dependency functions."""

from backend.api.middleware.plan_gate import PlanGateMiddleware
from backend.api.middleware.quota import QuotaMiddleware, check_insight_quota
from backend.api.middleware.rate_limit import RateLimitMiddleware, rate_limit_check

__all__ = [
    "PlanGateMiddleware",
    "RateLimitMiddleware",
    "QuotaMiddleware",
    "rate_limit_check",
    "check_insight_quota",
]
