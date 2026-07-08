import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from arena.models.user import User
from arena.models.api_key import ApiKey
from arena.auth.jwt import decode_access_token
from arena.auth.apikey import PLATFORM_KEY_PREFIX, hash_platform_key
from arena.db import get_db

LOCAL_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _providers_configured() -> bool:
    gh = bool(os.environ.get("GITHUB_CLIENT_ID", "").strip() and os.environ.get("GITHUB_CLIENT_SECRET", "").strip())
    goog = bool(os.environ.get("GOOGLE_CLIENT_ID", "").strip() and os.environ.get("GOOGLE_CLIENT_SECRET", "").strip())
    return gh or goog


async def _ensure_local_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == LOCAL_USER_ID))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=LOCAL_USER_ID,
            email="local@outplayarena.local",
            name="Local User",
            provider="local",
            provider_user_id="local",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="authentication required")

    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing token")

    if token.startswith(PLATFORM_KEY_PREFIX):
        return await _get_user_from_api_key(token, db)

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="user not found")

    return user


async def _get_user_from_api_key(token: str, db: AsyncSession) -> User:
    key_hash = hash_platform_key(token)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active,
            (ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > func.now()),
        )
    )
    key_row = result.scalar_one_or_none()
    if key_row is None:
        raise HTTPException(status_code=401, detail="invalid or expired API key")

    key_row.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    user_result = await db.execute(select(User).where(User.id == key_row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")

    return user


async def get_optional_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    try:
        return await get_current_user(authorization, db)
    except HTTPException:
        return None


async def get_local_or_optional_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if _providers_configured():
        return await get_optional_user(authorization, db)
    return await _ensure_local_user(db)


async def require_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if _providers_configured():
        return await get_current_user(authorization, db)
    return await _ensure_local_user(db)


def _is_admin_enabled() -> bool:
    """Read the ENABLE_ADMIN_DASHBOARD env toggle (#116)."""
    from arena.settings import get_settings

    return bool(get_settings().enable_admin_dashboard)


def _user_is_admin(user: User) -> bool:
    """Admin if the DB flag is set OR the user's UUID is in ADMIN_USER_IDS."""
    from arena.settings import get_settings

    if getattr(user, "is_admin", False):
        return True
    return str(user.id).lower() in get_settings().admin_user_id_set


async def require_admin(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Gate for /api/admin/* endpoints (#116).

    Returns the authenticated user if: the dashboard is enabled via
    ``ENABLE_ADMIN_DASHBOARD``, the caller is authenticated (per
    :func:`require_user`), and the user is an admin (``is_admin`` column
    OR in ``ADMIN_USER_IDS``). Otherwise raises 403.
    """
    if not _is_admin_enabled():
        raise HTTPException(status_code=403, detail="admin dashboard disabled")
    user = await require_user(authorization, db)
    if not _user_is_admin(user):
        raise HTTPException(status_code=403, detail="admin access required")
    return user
