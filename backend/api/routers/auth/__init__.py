"""Auth router package.

Aggregates all auth sub-routers and re-exports symbols that external code
(including tests) patch via ``backend.api.routers.auth.*``.

Import order matters: re-exports must be defined BEFORE sub-modules are
imported so that sub-modules can safely reference this package's namespace
at call time without hitting partially-initialised attributes.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.routers.auth._constants import (
    _2FA_CHALLENGE_TTL_MINUTES,
    _EMAIL_VERIFY_PREFIX,
    _EMAIL_VERIFY_TTL,
    _PASSWORD_RESET_PREFIX,
    _PASSWORD_RESET_TTL,
)

# ---------------------------------------------------------------------------
# Re-export symbols that tests patch as ``backend.api.routers.auth.<name>``.
# These must appear BEFORE sub-module imports so that ``_auth_pkg.*`` lookups
# inside oauth.py / password.py / verify.py resolve correctly even during the
# partially-initialised import phase.
# isort: split — keeps this block separate from the sub-module imports below.
# ---------------------------------------------------------------------------
from backend.auth.google_oauth import exchange_code, fetch_userinfo  # isort: skip
from backend.auth.kakao_oauth import exchange_kakao_code, fetch_kakao_userinfo  # isort: skip
from backend.auth.token_store import delete_auth_token, get_auth_token, save_auth_token  # isort: skip

# ---------------------------------------------------------------------------
# Sub-module imports — intentionally after the re-exports above.
# isort: split — keeps this block separate from the re-exports above.
# ---------------------------------------------------------------------------
from backend.api.routers.auth import basic, oauth, password, twofa, verify  # isort: skip

# ---------------------------------------------------------------------------
# Aggregate router — prefix "/auth" is set here so sub-modules stay clean
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/auth", tags=["auth"])

router.include_router(basic.router)
router.include_router(oauth.router)
router.include_router(twofa.router)
router.include_router(password.router)
router.include_router(verify.router)

__all__ = [
    "router",
    # constants
    "_EMAIL_VERIFY_PREFIX",
    "_EMAIL_VERIFY_TTL",
    "_PASSWORD_RESET_PREFIX",
    "_PASSWORD_RESET_TTL",
    "_2FA_CHALLENGE_TTL_MINUTES",
    # re-exported for test patching
    "exchange_code",
    "fetch_userinfo",
    "exchange_kakao_code",
    "fetch_kakao_userinfo",
    "get_auth_token",
    "save_auth_token",
    "delete_auth_token",
]
