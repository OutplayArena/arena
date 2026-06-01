import pytest

from nash_arena.auth import (
    AuthError,
    create_player_token,
    create_token,
    decode_player_token,
    decode_token,
    require_claims,
)


def test_create_token_returns_signed_jwt_with_expected_claims(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_JWT_SECRET", "test-secret")

    token = create_token(
        {"session_id": "s1", "player": "A", "scope": "game:action"},
        expires_in_seconds=60,
        now=100,
    )

    assert token.count(".") == 2
    assert decode_token(token, now=120) == {
        "session_id": "s1",
        "player": "A",
        "scope": "game:action",
        "iat": 100,
        "exp": 160,
    }


def test_decode_token_rejects_tampered_signature(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_JWT_SECRET", "test-secret")
    token = create_token({"session_id": "s1"}, expires_in_seconds=60, now=100)
    tampered = f"{token[:-1]}x"

    with pytest.raises(AuthError, match="signature"):
        decode_token(tampered, now=120)


def test_decode_token_rejects_expired_token(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_JWT_SECRET", "test-secret")
    token = create_token({"session_id": "s1"}, expires_in_seconds=10, now=100)

    with pytest.raises(AuthError, match="expired"):
        decode_token(token, now=110)


def test_require_claims_rejects_unexpected_claims(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_JWT_SECRET", "test-secret")
    token = create_token({"session_id": "s1", "scope": "game:action"})

    with pytest.raises(AuthError, match="claims"):
        require_claims(token, {"session_id": "other"})


def test_player_token_is_bound_to_session(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_JWT_SECRET", "test-secret")
    token = create_player_token(session_id="s1", player="A")

    assert decode_player_token(token, session_id="s1")["player"] == "A"
    with pytest.raises(AuthError, match="claims"):
        decode_player_token(token, session_id="s2")
