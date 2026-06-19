import base64

from cryptography.fernet import Fernet

from outplaylabs_arena.auth import JWT_SECRET


def _derive_key() -> bytes:
    raw = JWT_SECRET.encode("utf-8")
    key = base64.urlsafe_b64encode(raw.ljust(32, b"\x00")[:32])
    return key


_fernet = Fernet(_derive_key())


def encrypt_value(value: str) -> str:
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
