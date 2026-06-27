import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arena.models.user import User

_oauth_log = logging.getLogger("arena.auth.oauth")

# Read OAUTH_CALLBACK_BASE_URL from .env directly so a stale shell export
# can't pollute the dev fallback. Falls back to os.environ, then default.
_ENV = dotenv_values(Path(__file__).resolve().parents[3] / ".env")
CALLBACK_BASE = (
    _ENV.get("OAUTH_CALLBACK_BASE_URL")
    or os.environ.get("OAUTH_CALLBACK_BASE_URL")
    or "http://localhost:8000"
)

# OAUTH_ALLOWED_BASES: comma-separated list of origins allowed as the OAuth
# callback base (e.g. "https://arena.core-aix.org"). When unset (dev), the
# Host header is trusted directly — set it in production to lock down the
# redirect_uri and prevent Host-header injection attacks.
_ALLOWED_CALLBACK_BASES: frozenset[str] = frozenset(
    b.strip()
    for b in os.environ.get("OAUTH_ALLOWED_BASES", "").split(",")
    if b.strip()
)

oauth = OAuth()
oauth.register(
    name="github",
    client_id=os.environ.get("GITHUB_CLIENT_ID", ""),
    client_secret=os.environ.get("GITHUB_CLIENT_SECRET", ""),
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    access_token_url="https://accounts.google.com/o/oauth2/token",
    api_base_url="https://www.googleapis.com/",
    client_kwargs={"scope": "email profile"},
)


def _github_client() -> StarletteOAuth2App:
    return oauth.github  # type: ignore[no-any-return]


def _google_client() -> StarletteOAuth2App:
    return oauth.google  # type: ignore[no-any-return]


async def _upsert_user(db: AsyncSession, provider: str, provider_user_id: str, email: str, name: str, avatar_url: str | None) -> User:
    result = await db.execute(
        select(User).where(User.provider == provider, User.provider_user_id == provider_user_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.email = email
        user.name = name
        user.avatar_url = avatar_url
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
    else:
        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name,
            avatar_url=avatar_url,
            provider=provider,
            provider_user_id=provider_user_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


def _callback_base_for(request: Any) -> str:
    """Build the OAuth callback base URL.

    When OAUTH_ALLOWED_BASES is set (production), only origins in that list are
    accepted — anything else falls back to OAUTH_CALLBACK_BASE_URL, preventing
    Host-header injection from redirecting OAuth callbacks to attacker domains.

    When OAUTH_ALLOWED_BASES is unset (dev), the Host header is trusted
    directly so any LAN IP, Tailscale MagicDNS name, or localhost works
    without extra config.
    """
    host = request.headers.get("host")
    if host:
        scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
        candidate = f"{scheme}://{host}"
        if _ALLOWED_CALLBACK_BASES:
            if candidate in _ALLOWED_CALLBACK_BASES:
                return candidate
            _oauth_log.warning(
                "OAuth callback Host rejected: %r not in OAUTH_ALLOWED_BASES; "
                "falling back to OAUTH_CALLBACK_BASE_URL",
                candidate,
            )
        else:
            # Dev: no allowlist configured — trust the Host header as-is.
            return candidate
    return CALLBACK_BASE.rstrip("/") or f"{request.url.scheme}://{request.url.netloc}"


async def github_login(request: Any) -> str:
    redirect_uri = f"{_callback_base_for(request)}/api/auth/github/callback"
    client = _github_client()
    return await client.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


async def github_callback(request: Any, db: AsyncSession) -> User:
    client = _github_client()
    token = await client.authorize_access_token(request)
    resp = await client.get("user", token=token)
    profile = resp.json()

    email = profile.get("email")
    if not email:
        emails_resp = await client.get("user/emails", token=token)
        emails = emails_resp.json()
        primary = next((e for e in emails if e.get("primary")), emails[0] if emails else {})
        email = primary.get("email", "")

    name = profile.get("name") or profile.get("login", "")
    avatar_url = profile.get("avatar_url")

    return await _upsert_user(
        db,
        provider="github",
        provider_user_id=str(profile["id"]),
        email=email,
        name=name,
        avatar_url=avatar_url,
    )


async def google_login(request: Any) -> str:
    redirect_uri = f"{_callback_base_for(request)}/api/auth/google/callback"
    client = _google_client()
    return await client.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


async def google_callback(request: Any, db: AsyncSession) -> User:
    client = _google_client()
    token = await client.authorize_access_token(request)
    resp = await client.get("oauth2/v3/userinfo", token=token)
    userinfo = resp.json()

    return await _upsert_user(
        db,
        provider="google",
        provider_user_id=userinfo["sub"],
        email=userinfo.get("email", ""),
        name=userinfo.get("name", ""),
        avatar_url=userinfo.get("picture"),
    )
