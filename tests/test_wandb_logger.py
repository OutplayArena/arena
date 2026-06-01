import secrets

import pytest

from nash_arena.integrations.wandb_logger import (
    ENCRYPTION_KEY_ENV,
    WandbConfigError,
    decrypt_api_key,
    encrypt_api_key,
    encryption_key_from_env,
)


def test_encrypt_decrypt_api_key_round_trip():
    key = secrets.token_bytes(32)

    encrypted = encrypt_api_key("wandb-secret", key=key)

    assert decrypt_api_key(encrypted, key=key) == "wandb-secret"


def test_encrypted_api_key_does_not_contain_plaintext():
    key = secrets.token_bytes(32)

    encrypted = encrypt_api_key("wandb-secret", key=key)

    assert "wandb-secret" not in encrypted
    assert encrypted != "wandb-secret"


def test_encryption_key_from_env_loads_32_byte_hex_key(monkeypatch):
    raw_key = secrets.token_bytes(32)
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, raw_key.hex())

    assert encryption_key_from_env() == raw_key


def test_encryption_key_from_env_rejects_missing_key(monkeypatch):
    monkeypatch.delenv(ENCRYPTION_KEY_ENV, raising=False)

    with pytest.raises(WandbConfigError, match="required"):
        encryption_key_from_env()


def test_encryption_key_from_env_rejects_non_hex_key(monkeypatch):
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, "not-hex")

    with pytest.raises(WandbConfigError, match="hex"):
        encryption_key_from_env()


def test_encryption_key_from_env_rejects_wrong_length_key(monkeypatch):
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, secrets.token_bytes(16).hex())

    with pytest.raises(WandbConfigError, match="32 bytes"):
        encryption_key_from_env()


def test_decrypt_api_key_rejects_wrong_key():
    encrypted = encrypt_api_key("wandb-secret", key=secrets.token_bytes(32))

    with pytest.raises(WandbConfigError, match="could not decrypt"):
        decrypt_api_key(encrypted, key=secrets.token_bytes(32))


def test_encrypt_api_key_rejects_empty_plaintext_key():
    with pytest.raises(WandbConfigError, match="required"):
        encrypt_api_key("", key=secrets.token_bytes(32))


def test_decrypt_api_key_rejects_invalid_ciphertext():
    with pytest.raises(WandbConfigError, match="invalid"):
        decrypt_api_key("bad", key=secrets.token_bytes(32))
