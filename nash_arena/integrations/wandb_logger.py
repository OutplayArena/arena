import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ENCRYPTION_KEY_ENV = "NASH_ARENA_WANDB_ENCRYPTION_KEY"


class WandbConfigError(ValueError):
    pass

def encryption_key_from_env() -> bytes:
    value = os.environ.get(ENCRYPTION_KEY_ENV)
    if not value:
        raise WandbConfigError(f"{ENCRYPTION_KEY_ENV} is required")

    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise WandbConfigError(f"{ENCRYPTION_KEY_ENV} must be hex") from exc

    if len(key) != 32:
        raise WandbConfigError(f"{ENCRYPTION_KEY_ENV} must be 32 bytes")

    return key


def encrypt_api_key(plaintext: str, key: bytes | None = None) -> str:
    if not isinstance(plaintext, str) or not plaintext.strip():
        raise WandbConfigError("wandb api key is required")

    aesgcm = AESGCM(key or encryption_key_from_env())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_api_key(encrypted: str, key: bytes | None = None) -> str:
    try:
        raw = base64.urlsafe_b64decode(encrypted.encode("ascii"))
    except (AttributeError, UnicodeEncodeError, binascii.Error) as exc:
        raise WandbConfigError("encrypted wandb api key is invalid") from exc

    if len(raw) <= 12:
        raise WandbConfigError("encrypted wandb api key is invalid")

    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key or encryption_key_from_env())

    try:
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as exc:
        raise WandbConfigError("could not decrypt wandb api key") from exc
