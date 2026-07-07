"""Async helpers for reading and writing ``platform_settings`` rows.

``get_platform_setting(key, db, cast=str)`` is the hot-path read used by
the concurrency-queue admission gate (#117). It checks the DB first and
falls back to the env-var-backed :class:`arena.settings.Settings`
default when the row is absent (the common case before an admin edits
anything via #116's dashboard).

``set_platform_setting(key, value, db, updated_by=None)`` upserts a row
and is the write path used by #116's ``PUT /api/admin/settings``.
"""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arena.models.platform_setting import PlatformSetting
from arena.settings import get_settings


async def get_platform_setting(
    key: str,
    db: AsyncSession,
    *,
    cast: Callable[[str], Any] = str,
) -> Any:
    """Return the typed value for *key*, DB-first then env-var default.

    ``cast`` is applied to the stored textual value (e.g. ``int`` for the
    concurrency knobs). The env-var fallback is read from the cached
    :class:`Settings` instance so operators get a sane default before any
    admin touches the DB.
    """
    row = (
        await db.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
    ).scalar_one_or_none()
    if row is not None:
        return cast(row.value)
    return _env_default(key, cast)


def _env_default(key: str, cast: Callable[[str], Any]) -> Any:
    """Resolve the env-var default for *key* from the Settings instance."""
    settings = get_settings()
    # Map the DB key to the Settings field name. They share the same
    # snake_case spelling (e.g. ``max_concurrent_sessions``).
    attr = getattr(settings, key, None)
    if attr is None:
        return None
    if cast is bool:
        # Stored as text in the DB; for the env fallback the Settings
        # already coerced it. Just return as-is.
        return bool(attr)
    if cast is int:
        return int(attr)
    return cast(str(attr))


async def set_platform_setting(
    key: str,
    value: Any,
    db: AsyncSession,
    *,
    updated_by: UUID | None = None,
) -> str:
    """Upsert *key* = str(*value*) and return the stored textual value."""
    text_value = str(value).lower() if isinstance(value, bool) else str(value)
    row = (
        await db.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
    ).scalar_one_or_none()
    if row is None:
        row = PlatformSetting(key=key, value=text_value, updated_by=updated_by)
        db.add(row)
    else:
        row.value = text_value
        row.updated_by = updated_by
    await db.commit()
    return text_value


__all__ = ["get_platform_setting", "set_platform_setting"]