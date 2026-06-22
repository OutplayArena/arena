"""Tests for the JWT access token helpers."""

from jose import jwt

from arena.auth import JWT_ALGORITHM, JWT_SECRET
from arena.auth.jwt import create_access_token, decode_access_token


def test_create_access_token_returns_jwt_string():
    token = create_access_token("user-123")
    assert isinstance(token, str)
    assert token.count(".") == 2  # JWT format: header.payload.signature


def test_create_access_token_contains_user_id():
    token = create_access_token("user-456")
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "user-456"


def test_decode_access_token_returns_user_id():
    token = create_access_token("user-789")
    user_id = decode_access_token(token)
    assert user_id == "user-789"


def test_decode_access_token_returns_none_for_invalid():
    assert decode_access_token("not.a.valid.jwt") is None


def test_decode_access_token_returns_none_for_wrong_secret():
    token = jwt.encode({"sub": "user-1"}, "wrong-secret", algorithm=JWT_ALGORITHM)
    assert decode_access_token(token) is None


def test_decode_access_token_returns_none_for_expired(monkeypatch):
    """Expired tokens should be rejected."""
    import arena.auth.jwt as jwt_module

    original_create = jwt_module.jwt.encode

    def expired_encode(claims, secret, algorithm):
        from datetime import datetime, timedelta, timezone
        claims = dict(claims)
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=10)
        return original_create(claims, secret, algorithm)

    monkeypatch.setattr(jwt_module.jwt, "encode", expired_encode)
    token = create_access_token("user-expired")
    assert decode_access_token(token) is None


def test_decode_access_token_returns_none_for_missing_sub():
    """Token without sub claim should return None, not crash."""
    from datetime import datetime, timedelta, timezone
    payload = {"exp": datetime.now(timezone.utc) + timedelta(days=1)}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    assert decode_access_token(token) is None
