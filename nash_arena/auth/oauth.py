import os
import uuid
from datetime import datetime
from typing import Any

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nash_arena.models.user import User

CALLBACK_BASE = os.environ.get("OAUTH_CALLBACK_BASE_URL", "http://localhost:8000")

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
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
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
        user.last_login_at = datetime.utcnow()  # type: ignore[unused-awaitable]
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


async def github_login(request: Any) -> str:
    redirect_uri = f"{CALLBACK_BASE}/api/auth/github/callback"
    client = _github_client()
    return await client.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


async def github_callback(request: Any, db: AsyncSession) -> User:
    redirect_uri = f"{CALLBACK_BASE}/api/auth/github/callback"
    client = _github_client()
    token = await client.authorize_access_token(request, redirect_uri=redirect_uri)
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
    redirect_uri = f"{CALLBACK_BASE}/api/auth/google/callback"
    client = _google_client()
    return await client.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


async def google_callback(request: Any, db: AsyncSession) -> User:
    redirect_uri = f"{CALLBACK_BASE}/api/auth/google/callback"
    client = _google_client()
    token = await client.authorize_access_token(request, redirect_uri=redirect_uri)
    userinfo = token.get("userinfo")

    return await _upsert_user(
        db,
        provider="google",
        provider_user_id=userinfo["sub"],
        email=userinfo.get("email", ""),
        name=userinfo.get("name", ""),
        avatar_url=userinfo.get("picture"),
    )
