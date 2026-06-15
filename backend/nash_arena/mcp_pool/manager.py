import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from nash_arena.models.mcp_instance import McpInstance
from nash_arena.mcp_key_manager import create_mcp_key
from nash_arena.mcp_pool.runtime import ContainerRuntime

logger = logging.getLogger(__name__)


class PoolManager:
    def __init__(
        self,
        runtime: ContainerRuntime,
        max_concurrent: int = 50,
        job_ttl: int = 300,
        backend_url: str = "",
        image: str = "",
        port: int = 8000,
    ):
        self.runtime = runtime
        self.max_concurrent = max_concurrent
        self.job_ttl = job_ttl
        self.backend_url = backend_url
        self.image = image
        self.port = port

    async def assign_container(
        self,
        db: AsyncSession,
        session_id: str,
        session_key: str,
    ) -> McpInstance:
        """Assign an MCP container to a session. Spawn new if needed."""
        available = await self._get_available_instance(db)

        if available:
            available.session_id = session_id
            available.status = "busy"
            available.last_used_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"Assigned existing MCP instance {available.id} to session {session_id}")
            return available

        active_count = await self._count_active_instances(db)
        if active_count >= self.max_concurrent:
            raise RuntimeError(f"MCP pool exhausted ({self.max_concurrent} active instances)")

        return await self._spawn_new_instance(db, session_id, session_key)

    async def release_container(self, db: AsyncSession, session_id: str) -> None:
        """Release an MCP container back to the pool."""
        result = await db.execute(
            select(McpInstance).where(McpInstance.session_id == session_id)
        )
        instance = result.scalar_one_or_none()

        if not instance:
            logger.warning(f"No MCP instance found for session {session_id}")
            return

        instance.session_id = None
        instance.status = "available"
        instance.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Released MCP instance {instance.id} from session {session_id}")

    async def cleanup_idle(self, db: AsyncSession) -> int:
        """Stop containers idle longer than job_ttl. Returns count stopped."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.job_ttl)

        result = await db.execute(
            select(McpInstance).where(
                McpInstance.status == "available",
                McpInstance.last_used_at < cutoff,
            )
        )
        idle_instances = result.scalars().all()

        stopped = 0
        for instance in idle_instances:
            try:
                await self.runtime.stop(instance.container_name)
                instance.status = "stopped"
                instance.stopped_at = datetime.now(timezone.utc)
                await db.commit()
                stopped += 1
                logger.info(f"Cleaned up idle MCP instance {instance.id}")
            except Exception as e:
                logger.error(f"Failed to stop MCP instance {instance.id}: {e}")

        return stopped

    async def _get_available_instance(self, db: AsyncSession) -> McpInstance | None:
        """Get an available (idle) instance, preferring least recently used."""
        result = await db.execute(
            select(McpInstance)
            .where(McpInstance.status == "available")
            .order_by(McpInstance.last_used_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _count_active_instances(self, db: AsyncSession) -> int:
        """Count instances that are starting or busy."""
        result = await db.execute(
            select(func.count(McpInstance.id)).where(
                McpInstance.status.in_(["starting", "busy"])
            )
        )
        return result.scalar()

    async def _spawn_new_instance(
        self,
        db: AsyncSession,
        session_id: str,
        session_key: str,
    ) -> McpInstance:
        """Spawn a new MCP container and track it in the database."""
        container_name = f"mcp-{uuid.uuid4().hex[:12]}"

        full_key, key_row = await create_mcp_key(db, name=f"session-{session_id}")

        try:
            container_info = await self.runtime.spawn(
                container_name=container_name,
                mcp_auth_key=full_key,
                backend_url=self.backend_url,
                session_key=session_key,
                image=self.image,
                port=self.port,
            )
        except Exception:
            await db.delete(key_row)
            await db.commit()
            raise

        instance = McpInstance(
            id=uuid.uuid4(),
            key_id=key_row.id,
            session_id=session_id,
            status="busy",
            runtime="k8s" if hasattr(self.runtime, 'namespace') else "docker",
            container_name=container_info.container_name,
            dns_name=container_info.dns_name,
            port=container_info.port,
            public_url=container_info.public_url,
            last_used_at=datetime.now(timezone.utc),
        )

        db.add(instance)
        await db.commit()
        await db.refresh(instance)

        logger.info(f"Spawned new MCP instance {instance.id} for session {session_id}")
        return instance
