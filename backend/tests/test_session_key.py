"""Tests for session key derivation and validation."""
import pytest

from nash_arena.auth.session_key import (
    SESSION_KEY_PREFIX,
    derive_session_key,
    validate_session_key,
)


class TestSessionKey:
    def test_derive_and_validate_roundtrip(self):
        session_id = "abc-123-def"
        player = "A"
        key = derive_session_key(session_id, player)

        result_id, result_player = validate_session_key(key)
        assert result_id == session_id
        assert result_player == player

    def test_derive_produces_prefix(self):
        key = derive_session_key("session", "B")
        assert key.startswith(SESSION_KEY_PREFIX)

    def test_derive_different_players_different_keys(self):
        key_a = derive_session_key("session", "A")
        key_b = derive_session_key("session", "B")
        assert key_a != key_b

    def test_derive_different_sessions_different_keys(self):
        key_1 = derive_session_key("session-1", "A")
        key_2 = derive_session_key("session-2", "A")
        assert key_1 != key_2

    def test_validate_invalid_prefix(self):
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key("invalid_key")

    def test_validate_empty_key(self):
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key("")

    def test_validate_none_key(self):
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(None)

    def test_validate_tampered_key(self):
        key = derive_session_key("session", "A")
        tampered = key[:-2] + "XX"
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(tampered)

    def test_validate_malformed_base64(self):
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(f"{SESSION_KEY_PREFIX}!!!invalid!!!")

    def test_validate_wrong_part_count(self):
        import base64
        token = base64.urlsafe_b64encode(b"only:two").decode("utf-8").rstrip("=")
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(f"{SESSION_KEY_PREFIX}{token}")

    def test_validate_wrong_signature(self):
        import base64
        import hashlib
        import hmac
        from nash_arena.auth import JWT_SECRET

        hashlib.sha256(JWT_SECRET.encode("utf-8")).digest()
        payload = "session:A"
        wrong_sig = hmac.new(b"wrong-secret", payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"session:A:{wrong_sig}"
        encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8").rstrip("=")

        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(f"{SESSION_KEY_PREFIX}{encoded}")
