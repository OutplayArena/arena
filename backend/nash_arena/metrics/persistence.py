from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from nash_arena.metrics.registry import AgentRegistry
from nash_arena.models.agent_registry import AgentRegistryState


async def load_registry(db: AsyncSession, key: str = "global") -> AgentRegistry:
    result = await db.execute(
        select(AgentRegistryState).where(AgentRegistryState.key == key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return AgentRegistry()
    return AgentRegistry.from_dict(row.state_json)


async def save_registry(registry: AgentRegistry, db: AsyncSession, key: str = "global") -> None:
    state = registry.to_dict()
    stmt = pg_insert(AgentRegistryState).values(
        key=key,
        state_json=state,
    ).on_conflict_do_update(
        index_elements=["key"],
        set_={"state_json": state},
    )
    await db.execute(stmt)
    await db.commit()
