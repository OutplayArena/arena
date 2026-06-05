import hashlib
import secrets


PLATFORM_KEY_PREFIX = "nka_"


def generate_platform_key() -> tuple[str, str, str]:
    suffix = secrets.token_urlsafe(32)
    full_key = f"{PLATFORM_KEY_PREFIX}{suffix}"
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    key_prefix = full_key[: len(PLATFORM_KEY_PREFIX) + 8]
    return full_key, key_hash, key_prefix


def hash_platform_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
