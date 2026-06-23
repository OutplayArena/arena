"""Tests for the platform API key helpers."""
import hashlib

from arena.auth.apikey import (
    PLATFORM_KEY_PREFIX,
    generate_platform_key,
    hash_platform_key,
)


def test_generate_platform_key_returns_three_strings():
    full_key, key_hash, key_prefix = generate_platform_key()
    assert isinstance(full_key, str)
    assert isinstance(key_hash, str)
    assert isinstance(key_prefix, str)


def test_generate_platform_key_starts_with_prefix():
    full_key, _, _ = generate_platform_key()
    assert full_key.startswith(PLATFORM_KEY_PREFIX)


def test_generate_platform_key_hash_is_sha256_hex():
    full_key, key_hash, _ = generate_platform_key()
    expected = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    assert key_hash == expected
    assert len(key_hash) == 64  # SHA-256 hex digest length


def test_generate_platform_key_prefix_length():
    _, _, key_prefix = generate_platform_key()
    assert len(key_prefix) == len(PLATFORM_KEY_PREFIX) + 8


def test_generate_platform_key_prefix_matches_full_key():
    full_key, _, key_prefix = generate_platform_key()
    assert full_key[: len(key_prefix)] == key_prefix


def test_generate_platform_key_uniqueness():
    keys = {generate_platform_key()[0] for _ in range(100)}
    assert len(keys) == 100  # All unique


def test_hash_platform_key_matches_generate():
    full_key, key_hash, _ = generate_platform_key()
    assert hash_platform_key(full_key) == key_hash


def test_hash_platform_key_is_deterministic():
    key = f"{PLATFORM_KEY_PREFIX}fixed-test-key-value"
    h1 = hash_platform_key(key)
    h2 = hash_platform_key(key)
    assert h1 == h2
    assert len(h1) == 64
