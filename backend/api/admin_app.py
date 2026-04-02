"""Admin sub-application — internal-only routes.

Mounted at /admin by the main app, so all router prefixes start with /v1.
The final URL paths remain /admin/v1/... (backwards compatible).
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from backend.api.routers.admin import ai_config as admin_ai_config
from backend.api.routers.admin import analytics as admin_analytics
from backend.api.routers.admin import audit as admin_audit
from backend.api.routers.admin import feed_sources as admin_feed_sources
from backend.api.routers.admin import quota_alerts as admin_quota_alerts
from backend.api.routers.admin import settings as admin_settings
from backend.api.routers.admin import sources as admin_sources
from backend.api.routers.admin import subscriptions as admin_subscriptions
from backend.api.routers.admin import users as admin_users

logger = structlog.get_logger(__name__)


def create_admin_app() -> FastAPI:
    """Create the admin sub-application with its own middleware stack.

    The app is intended to be mounted at /admin on the main app:
        main_app.mount("/admin", create_admin_app())

    DB pool and Redis are shared via state propagation in the main app lifespan.
    """
    admin = FastAPI(
        title="TrendScope Admin API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # All routers use /v1 prefix; when mounted at /admin the final path is /admin/v1/...
    admin.include_router(admin_users.router, prefix="/v1")
    admin.include_router(admin_subscriptions.router, prefix="/v1")
    admin.include_router(admin_sources.router, prefix="/v1")
    admin.include_router(admin_feed_sources.router, prefix="/v1")
    admin.include_router(admin_ai_config.router, prefix="/v1")
    admin.include_router(admin_settings.router, prefix="/v1")
    admin.include_router(admin_audit.router, prefix="/v1")
    admin.include_router(admin_analytics.router, prefix="/v1")
    admin.include_router(admin_quota_alerts.router, prefix="/v1")

    try:
        from backend.api.routers.admin import error_logs as admin_error_logs

        admin.include_router(admin_error_logs.router, prefix="/v1")
        logger.info("admin_error_logs_router_registered")
    except ImportError:
        logger.debug("admin_error_logs_router_not_found_skipped")

    return admin
