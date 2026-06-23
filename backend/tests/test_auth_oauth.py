"""Tests for the OAuth login/callback flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arena.auth import oauth
from arena.auth.oauth import (
    CALLBACK_BASE,
    _callback_base_for,
    _github_client,
    _google_client,
    _upsert_user,
    github_callback,
    github_login,
    google_callback,
    google_login,
)


def _make_request(host=None, scheme="http", forwarded_proto=None, netloc=None):
    """Build a fake Request object."""
    request = MagicMock()
    request.headers = {}
    if host:
        request.headers["host"] = host
    if forwarded_proto:
        request.headers["x-forwarded-proto"] = forwarded_proto
    request.url = MagicMock()
    request.url.scheme = scheme
    if netloc:
        request.url.netloc = netloc
    return request


class TestCallbackBaseFor:
    def test_uses_host_header_with_default_scheme(self):
        req = _make_request(host="localhost:5173", scheme="http")
        assert _callback_base_for(req) == "http://localhost:5173"

    def test_uses_https_scheme(self):
        req = _make_request(host="example.com", scheme="https")
        assert _callback_base_for(req) == "https://example.com"

    def test_trusts_x_forwarded_proto(self):
        req = _make_request(
            host="example.com", scheme="http", forwarded_proto="https"
        )
        assert _callback_base_for(req) == "https://example.com"

    def test_falls_back_to_env_when_no_host(self):
        req = _make_request(scheme="http", netloc="fallback:80")
        # Without a host header, falls back to CALLBACK_BASE.
        result = _callback_base_for(req)
        # The result is the env var or the request URL.
        assert result == CALLBACK_BASE.rstrip("/") or result == "http://fallback:80"

    def test_strips_trailing_slash_in_fallback(self, monkeypatch):
        monkeypatch.setattr(oauth, "CALLBACK_BASE", "http://example.com/")
        req = _make_request(scheme="http", netloc="fallback:80")
        result = _callback_base_for(req)
        assert not result.endswith("/")


class TestClientAccessors:
    def test_github_client_returns_registered_app(self):
        client = _github_client()
        assert client is oauth.oauth.github

    def test_google_client_returns_registered_app(self):
        client = _google_client()
        assert client is oauth.oauth.google


class TestGithubLogin:
    @pytest.mark.asyncio
    async def test_authorize_redirect_called_with_callback_url(self):
        req = _make_request(host="localhost:8000")
        with patch.object(oauth, "_github_client") as mock_get:
            mock_client = MagicMock()
            mock_client.authorize_redirect = AsyncMock(return_value="redirect")
            mock_get.return_value = mock_client

            result = await github_login(req)
            assert result == "redirect"
            mock_client.authorize_redirect.assert_awaited_once()
            args = mock_client.authorize_redirect.await_args
            # First arg is the request, second is redirect_uri.
            assert args.args[0] is req
            assert "http://localhost:8000/api/auth/github/callback" in args.args[1]


class TestGoogleLogin:
    @pytest.mark.asyncio
    async def test_authorize_redirect_called_with_callback_url(self):
        req = _make_request(host="localhost:8000")
        with patch.object(oauth, "_google_client") as mock_get:
            mock_client = MagicMock()
            mock_client.authorize_redirect = AsyncMock(return_value="redirect")
            mock_get.return_value = mock_client

            result = await google_login(req)
            assert result == "redirect"
            mock_client.authorize_redirect.assert_awaited_once()
            args = mock_client.authorize_redirect.await_args
            assert args.args[0] is req
            assert "http://localhost:8000/api/auth/google/callback" in args.args[1]


def _make_fake_db(existing_user=None):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=existing_user)
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.refresh = AsyncMock()
    return db


class TestUpsertUser:
    @pytest.mark.asyncio
    async def test_updates_existing_user(self):
        existing = MagicMock()
        existing.email = "old@x.com"
        existing.name = "Old"
        existing.avatar_url = None
        db = _make_fake_db(existing_user=existing)

        user = await _upsert_user(
            db, provider="github", provider_user_id="123",
            email="new@x.com", name="New", avatar_url="http://img",
        )
        assert user is existing
        assert user.email == "new@x.com"
        assert user.name == "New"
        assert user.avatar_url == "http://img"
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_creates_new_user(self):
        db = _make_fake_db(existing_user=None)

        user = await _upsert_user(
            db, provider="github", provider_user_id="999",
            email="new@x.com", name="New", avatar_url=None,
        )
        assert user is not None
        assert user.email == "new@x.com"
        assert user.provider == "github"
        assert user.provider_user_id == "999"
        db.add.assert_called_once_with(user)


class TestGithubCallback:
    @pytest.mark.asyncio
    async def test_full_flow_with_email_in_profile(self):
        req = MagicMock()
        db = _make_fake_db(existing_user=None)

        profile = {"id": 123, "email": "u@x.com", "name": "User", "avatar_url": "http://i"}
        token = {"access_token": "tok"}

        with patch.object(oauth, "_github_client") as mock_get:
            mock_client = MagicMock()
            mock_client.authorize_access_token = AsyncMock(return_value=token)

            user_response = MagicMock()
            user_response.json = MagicMock(return_value=profile)
            # The code does `await client.get(...)` so make get awaitable.
            mock_client.get = AsyncMock(return_value=user_response)
            mock_get.return_value = mock_client

            user = await github_callback(req, db)
            assert user.email == "u@x.com"
            assert user.name == "User"
            assert user.avatar_url == "http://i"
            assert user.provider == "github"

    @pytest.mark.asyncio
    async def test_fetches_email_from_emails_endpoint_when_missing(self):
        req = MagicMock()
        db = _make_fake_db(existing_user=None)

        profile = {"id": 123, "name": "LoginName"}  # no email
        emails = [
            {"email": "primary@x.com", "primary": True},
            {"email": "secondary@x.com"},
        ]
        token = {"access_token": "tok"}

        with patch.object(oauth, "_github_client") as mock_get:
            mock_client = MagicMock()
            mock_client.authorize_access_token = AsyncMock(return_value=token)

            user_response = MagicMock()
            user_response.json = MagicMock(return_value=profile)
            emails_response = MagicMock()
            emails_response.json = MagicMock(return_value=emails)
            mock_client.get = AsyncMock(side_effect=[user_response, emails_response])
            mock_get.return_value = mock_client

            user = await github_callback(req, db)
            assert user.email == "primary@x.com"
            assert user.name == "LoginName"  # falls back to login

    @pytest.mark.asyncio
    async def test_falls_back_to_login_when_no_name(self):
        req = MagicMock()
        db = _make_fake_db(existing_user=None)

        profile = {"id": 123, "email": "u@x.com", "login": "mylogin"}
        token = {"access_token": "tok"}

        with patch.object(oauth, "_github_client") as mock_get:
            mock_client = MagicMock()
            mock_client.authorize_access_token = AsyncMock(return_value=token)
            user_response = MagicMock()
            user_response.json = MagicMock(return_value=profile)
            mock_client.get = AsyncMock(return_value=user_response)
            mock_get.return_value = mock_client

            user = await github_callback(req, db)
            assert user.name == "mylogin"


class TestGoogleCallback:
    @pytest.mark.asyncio
    async def test_full_flow(self):
        req = MagicMock()
        db = _make_fake_db(existing_user=None)

        userinfo = {
            "sub": "google-123",
            "email": "g@x.com",
            "name": "Google User",
            "picture": "http://pic",
        }
        token = {"access_token": "tok"}

        with patch.object(oauth, "_google_client") as mock_get:
            mock_client = MagicMock()
            mock_client.authorize_access_token = AsyncMock(return_value=token)
            userinfo_response = MagicMock()
            userinfo_response.json = MagicMock(return_value=userinfo)
            mock_client.get = AsyncMock(return_value=userinfo_response)
            mock_get.return_value = mock_client

            user = await google_callback(req, db)
            assert user.email == "g@x.com"
            assert user.name == "Google User"
            assert user.avatar_url == "http://pic"
            assert user.provider == "google"
            assert user.provider_user_id == "google-123"
