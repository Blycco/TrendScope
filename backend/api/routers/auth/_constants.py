"""Shared constants for auth sub-modules."""

from __future__ import annotations

_EMAIL_VERIFY_PREFIX = "email_verify"
_EMAIL_VERIFY_TTL = 3600  # 1 hour
_PASSWORD_RESET_PREFIX = "password_reset"  # noqa: S105
_PASSWORD_RESET_TTL = 3600  # 1 hour
_2FA_CHALLENGE_TTL_MINUTES = 5
