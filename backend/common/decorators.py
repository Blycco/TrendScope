"""Reusable endpoint decorators. (RULE 06: try/except + structlog, RULE 07: type hints)"""

from __future__ import annotations

import types
from collections.abc import Callable
from functools import wraps
from typing import Any

import structlog
from fastapi import HTTPException

from backend.common.errors import ErrorCode, error_response

logger = structlog.get_logger(__name__)

# Keep a module-level reference so the merged globals can always find HTTPException
_MODULE_GLOBALS = globals()


def handle_errors(
    error_code: ErrorCode = ErrorCode.DB_ERROR,
    message: str = "Internal server error",
    status_code: int = 500,
    log_event: str | None = None,
) -> Callable:
    """Decorator that wraps an async endpoint with unified error handling.

    - HTTPException is re-raised as-is (preserves explicit API errors).
    - Any other Exception is logged and converted to a structured error_response.
    - Auto-logs 5xx errors to error_log table via error_response().

    NOTE: The wrapper is rebound with merged globals (original function's globals
    overlaid on the decorator module's globals) so that:
    1. FastAPI can resolve forward-reference type annotations (``from __future__
       import annotations``) using the endpoint module's namespace.
    2. The wrapper code can still access ``HTTPException`` and other names
       captured from the decorator module.

    Usage::

        @router.get("/items")
        @handle_errors(log_event="items_fetch_failed")
        async def list_items(request: Request) -> ...:
            pool = request.app.state.db_pool
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as exc:
                event = log_event or f"{func.__name__}_failed"
                logger.error(event, error=str(exc))
                return error_response(error_code, message, status_code=status_code)

        # Build merged globals: decorator module globals as base, then overlay the
        # original function's globals. This ensures:
        # - HTTPException and other decorator-module names are available for the
        #   wrapper bytecode.
        # - All names from the endpoint module (including FastAPI types like
        #   Request, Depends, CurrentUser) are also available so that
        #   FastAPI's get_typed_signature() can resolve forward references.
        merged_globals = {**_MODULE_GLOBALS, **func.__globals__}

        rebound: Callable = types.FunctionType(
            wrapper.__code__,
            merged_globals,
            wrapper.__name__,
            wrapper.__defaults__,
            wrapper.__closure__,
        )
        rebound.__annotations__ = wrapper.__annotations__
        rebound.__wrapped__ = func
        rebound.__doc__ = func.__doc__
        rebound.__kwdefaults__ = wrapper.__kwdefaults__
        return rebound

    return decorator
