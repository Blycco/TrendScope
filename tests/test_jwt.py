"""Tests for backend/auth/jwt.py and auth/password.py."""

from __future__ import annotations

import jwt
import pytest

# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only")


class TestJwt:
    def test_access_token_roundtrip(self) -> None:
        from backend.auth.jwt import create_access_token, decode_token

        token = create_access_token("user-123", "pro", "marketer")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["plan"] == "pro"
        assert payload["role"] == "marketer"
        assert payload["type"] == "access"

    def test_refresh_token_roundtrip(self) -> None:
        from backend.auth.jwt import create_refresh_token, decode_token

        token = create_refresh_token("user-456")
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_expired_token_raises(self) -> None:
        # Create an already-expired token manually
        import time

        from backend.auth.jwt import ALGORITHM, _secret, decode_token

        payload = {"sub": "u", "exp": int(time.time()) - 10, "type": "access"}
        token = jwt.encode(payload, _secret(), algorithm=ALGORITHM)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)

    def test_invalid_signature_raises(self) -> None:
        from backend.auth.jwt import create_access_token, decode_token

        token = create_access_token("u", "free", "general")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(jwt.PyJWTError):
            decode_token(tampered)

    def test_missing_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        from backend.auth import jwt as jwt_mod

        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            jwt_mod._secret()


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------


class TestPassword:
    def test_hash_and_verify(self) -> None:
        from backend.auth.password import hash_password, verify_password

        hashed = hash_password("my-secret-password")
        assert verify_password("my-secret-password", hashed)

    def test_wrong_password_fails(self) -> None:
        from backend.auth.password import hash_password, verify_password

        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_hash_is_unique(self) -> None:
        from backend.auth.password import hash_password

        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # different salts
