from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nash_arena.auth.apikey import generate_mcp_key
from nash_arena.models.mcp_auth_key import McpAuthKey


async def create_mcp_key(db: AsyncSession, name: str | None = None) -> tuple[str, McpAuthKey]:
    full_key, key_hash, key_prefix = generate_mcp_key()
    row = McpAuthKey(
        id=uuid4(),
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return full_key, row


async def revoke_mcp_key(db: AsyncSession, key_id: str) -> bool:
    result = await db.execute(select(McpAuthKey).where(McpAuthKey.id == key_id))
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def disable_mcp_key(db: AsyncSession, key_id: str) -> bool:
    result = await db.execute(select(McpAuthKey).where(McpAuthKey.id == key_id))
    row = result.scalar_one_or_none()
    if row is None:
        return False
    row.is_active = False
    await db.commit()
    return True


async def enable_mcp_key(db: AsyncSession, key_id: str) -> bool:
    result = await db.execute(select(McpAuthKey).where(McpAuthKey.id == key_id))
    row = result.scalar_one_or_none()
    if row is None:
        return False
    row.is_active = True
    await db.commit()
    return True


async def list_mcp_keys(db: AsyncSession) -> list[McpAuthKey]:
    result = await db.execute(select(McpAuthKey).order_by(McpAuthKey.created_at.desc()))
    return list(result.scalars().all())
