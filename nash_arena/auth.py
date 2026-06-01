import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


JWT_SECRET_ENV = "NASH_ARENA_JWT_SECRET"
JWT_ALGORITHM_ENV = "NASH_ARENA_JWT_ALGORITHM"
PLAYER_TOKEN_TTL_ENV = "NASH_ARENA_PLAYER_TOKEN_TTL_SECONDS"
DEFAULT_JWT_SECRET = "dev-secret-change-me"
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_PLAYER_TOKEN_TTL_SECONDS = 24 * 60 * 60
PLAYER_ACTION_SCOPE = "game:action"


class AuthError(ValueError):
    pass


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def _jwt_secret() -> bytes:
    return os.environ.get(JWT_SECRET_ENV, DEFAULT_JWT_SECRET).encode("utf-8")


def _jwt_algorithm() -> str:
    return os.environ.get(JWT_ALGORITHM_ENV, DEFAULT_JWT_ALGORITHM)


def _player_token_ttl_seconds() -> int:
    return int(os.environ.get(PLAYER_TOKEN_TTL_ENV, DEFAULT_PLAYER_TOKEN_TTL_SECONDS))


def _sign(message: bytes) -> str:
    return _base64url_encode(hmac.new(_jwt_secret(), message, hashlib.sha256).digest())


# Create a signed JWT with standard issue and expiry claims.
def create_token(
    claims: dict[str, Any],
    expires_in_seconds: int | None = None,
    now: int | None = None,
) -> str:
    algorithm = _jwt_algorithm()
    if algorithm != "HS256":
        raise AuthError(f"unsupported JWT algorithm: {algorithm}")

    issued_at = int(time.time() if now is None else now)
    ttl = _player_token_ttl_seconds() if expires_in_seconds is None else expires_in_seconds
    header = {"typ": "JWT", "alg": algorithm}
    payload = {
        **claims,
        "iat": issued_at,
        "exp": issued_at + ttl,
    }

    encoded_header = _base64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = _sign(signing_input)

    return f"{encoded_header}.{encoded_payload}.{signature}"


# Decode and verify a JWT signature, algorithm, and expiry time.
def decode_token(token: str, now: int | None = None) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, signature = token.split(".")
    except ValueError as exc:
        raise AuthError("invalid token format") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthError("invalid token signature")

    try:
        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AuthError("invalid token payload") from exc

    if header.get("alg") != _jwt_algorithm():
        raise AuthError("invalid token algorithm")
    if header.get("typ") != "JWT":
        raise AuthError("invalid token type")

    current_time = int(time.time() if now is None else now)
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or current_time >= expires_at:
        raise AuthError("token expired")

    return payload


# Verify that a token contains the expected claims before trusting it.
def require_claims(
    token: str,
    expected_claims: dict[str, Any],
    now: int | None = None,
) -> dict[str, Any]:
    payload = decode_token(token, now=now)
    for key, expected_value in expected_claims.items():
        if payload.get(key) != expected_value:
            raise AuthError("invalid token claims")
    return payload


# Create a player-scoped token for submitting actions in one session.
def create_player_token(session_id: str, player: str) -> str:
    return create_token(
        {
            "session_id": session_id,
            "player": player,
            "scope": PLAYER_ACTION_SCOPE,
        }
    )


# Decode a player token and ensure it belongs to the requested session.
def decode_player_token(token: str, session_id: str) -> dict[str, Any]:
    return require_claims(
        token,
        {
            "session_id": session_id,
            "scope": PLAYER_ACTION_SCOPE,
        },
    )
