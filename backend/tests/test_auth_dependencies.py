"""Tests for the auth dependencies (get_current_user, require_user, etc.)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from arena.auth.apikey import PLATFORM_KEY_PREFIX, generate_platform_key
from arena.auth.dependencies import (
    LOCAL_USER_ID,
    _ensure_local_user,
    _providers_configured,
    get_current_user,
    get_local_or_optional_user,
    get_optional_user,
    require_user,
)
from arena.auth.jwt import create_access_token


def _make_fake_user(user_id=None, email="u@example.com"):
    user = MagicMock()
    user.id = user_id or uuid4()
    user.email = email
    user.name = "Test User"
    user.avatar_url = None
    return user


def _make_fake_api_key(user_id, expired=False, inactive=False):
    key = MagicMock()
    key.user_id = user_id
    key.is_active = not inactive
    key.expires_at = (
        datetime.now(timezone.utc) - timedelta(days=1) if expired
        else None
    )
    key.last_used_at = None
    return key


class TestProvidersConfigured:
    def test_no_providers(self, monkeypatch):
        monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        assert _providers_configured() is False

    def test_github_configured(self, monkeypatch):
        monkeypatch.setenv("GITHUB_CLIENT_ID", "x")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "y")
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        assert _providers_configured() is True

    def test_google_configured(self, monkeypatch):
        monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "y")
        assert _providers_configured() is True

    def test_empty_github_id_not_configured(self, monkeypatch):
        monkeypatch.setenv("GITHUB_CLIENT_ID", "")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "y")
        assert _providers_configured() is False


class TestEnsureLocalUser:
    @pytest.mark.asyncio
    async def test_returns_existing_user(self):
        existing = _make_fake_user(user_id=LOCAL_USER_ID)
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=existing)
        db.execute = AsyncMock(return_value=result_mock)

        user = await _ensure_local_user(db)
        assert user is existing
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_user_if_missing(self):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        user = await _ensure_local_user(db)
        assert user.id == LOCAL_USER_ID
        assert user.email == "local@outplayarena.local"
        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestGetCurrentUserJWT:
    @pytest.mark.asyncio
    async def test_missing_authorization_returns_401(self):
        db = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None, db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_bearer_token_returns_401(self):
        db = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Token abc", db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_bearer_with_empty_token_returns_401(self):
        db = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Bearer ", db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_jwt_returns_user(self):
        user_id = str(uuid4())
        token = create_access_token(user_id)
        user = _make_fake_user(user_id=UUID(user_id))
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=user)
        db.execute = AsyncMock(return_value=result_mock)

        result = await get_current_user(f"Bearer {token}", db)
        assert result is user

    @pytest.mark.asyncio
    async def test_invalid_jwt_returns_401(self):
        db = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Bearer not.a.valid.jwt", db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_jwt_unknown_user_returns_401(self):
        user_id = str(uuid4())
        token = create_access_token(user_id)
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(f"Bearer {token}", db)
        assert exc_info.value.status_code == 401


class TestGetCurrentUserAPIKey:
    @pytest.mark.asyncio
    async def test_valid_api_key_returns_user(self):
        full_key, key_hash, _ = generate_platform_key()
        user = _make_fake_user()
        key = _make_fake_api_key(user.id)

        db = MagicMock()
        results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=key)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
        ]
        db.execute = AsyncMock(side_effect=results)
        db.commit = AsyncMock()

        result = await get_current_user(f"Bearer {full_key}", db)
        assert result is user
        assert key.last_used_at is not None

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self):
        full_key = f"{PLATFORM_KEY_PREFIX}invalid-key-value"
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(f"Bearer {full_key}", db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_api_key_returns_401(self):
        full_key, _, _ = generate_platform_key()
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)  # filtered by is_active
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException):
            await get_current_user(f"Bearer {full_key}", db)

    @pytest.mark.asyncio
    async def test_expired_api_key_returns_401(self):
        full_key, _, _ = generate_platform_key()
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)  # filtered by expires_at
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException):
            await get_current_user(f"Bearer {full_key}", db)

    @pytest.mark.asyncio
    async def test_api_key_with_missing_user_returns_401(self):
        full_key, _, _ = generate_platform_key()
        user_id = uuid4()
        key = _make_fake_api_key(user_id)

        db = MagicMock()
        results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=key)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # user not found
        ]
        db.execute = AsyncMock(side_effect=results)
        db.commit = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(f"Bearer {full_key}", db)
        assert exc_info.value.status_code == 401


class TestGetOptionalUser:
    @pytest.mark.asyncio
    async def test_returns_none_on_missing_auth(self):
        db = MagicMock()
        result = await get_optional_user(None, db)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_on_valid_token(self):
        user_id = str(uuid4())
        token = create_access_token(user_id)
        user = _make_fake_user(user_id=UUID(user_id))
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=user)
        db.execute = AsyncMock(return_value=result_mock)

        result = await get_optional_user(f"Bearer {token}", db)
        assert result is user


class TestGetLocalOrOptionalUser:
    @pytest.mark.asyncio
    async def test_uses_local_when_no_providers(self, monkeypatch):
        monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

        local = _make_fake_user(user_id=LOCAL_USER_ID)
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=local)
        db.execute = AsyncMock(return_value=result_mock)

        result = await get_local_or_optional_user(None, db)
        assert result is local

    @pytest.mark.asyncio
    async def test_uses_oauth_when_providers_configured(self, monkeypatch):
        monkeypatch.setenv("GITHUB_CLIENT_ID", "x")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "y")

        # No auth header → returns None (optional behavior).
        db = MagicMock()
        result = await get_local_or_optional_user(None, db)
        assert result is None


class TestRequireUser:
    @pytest.mark.asyncio
    async def test_uses_local_when_no_providers(self, monkeypatch):
        monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
        monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

        local = _make_fake_user(user_id=LOCAL_USER_ID)
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=local)
        db.execute = AsyncMock(return_value=result_mock)

        result = await require_user(None, db)
        assert result is local

    @pytest.mark.asyncio
    async def test_uses_oauth_when_providers_configured(self, monkeypatch):
        monkeypatch.setenv("GITHUB_CLIENT_ID", "x")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "y")

        db = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await require_user(None, db)
        assert exc_info.value.status_code == 401
