import hashlib
import hmac
import secrets

from outplaylabs_arena.auth import JWT_SECRET


def _session_key_secret() -> bytes:
    return hashlib.sha256(JWT_SECRET.encode("utf-8")).digest()


# DUPLICATE: Also defined in agent-sdk/src/outplaylabs_arena_sdk/client.py
# Keep implementations in sync. The SDK version accepts secret as a parameter.
SESSION_KEY_PREFIX = "nks_"


def derive_session_key(session_id: str, player: str) -> str:
    payload = f"{session_id}:{player}"
    sig = hmac.new(
        _session_key_secret(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    token = f"{session_id}:{player}:{sig}"
    import base64

    encoded = (
        base64.urlsafe_b64encode(token.encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )
    return f"{SESSION_KEY_PREFIX}{encoded}"


# DUPLICATE: Also defined in agent-sdk/src/outplaylabs_arena_sdk/client.py
# Keep implementations in sync. The SDK version accepts secret as a parameter.
def validate_session_key(key: str) -> tuple[str, str]:
    import base64

    if not key or not key.startswith(SESSION_KEY_PREFIX):
        raise ValueError("invalid session key")

    encoded = key[len(SESSION_KEY_PREFIX) :]
    padding = 4 - (len(encoded) % 4)
    if padding != 4:
        encoded += "=" * padding
    try:
        token = base64.urlsafe_b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise ValueError("invalid session key")

    parts = token.split(":")
    if len(parts) != 3:
        raise ValueError("invalid session key")
    session_id, player, sig = parts

    payload = f"{session_id}:{player}"
    expected = hmac.new(
        _session_key_secret(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not secrets.compare_digest(sig, expected):
        raise ValueError("invalid session key")

    return session_id, player
