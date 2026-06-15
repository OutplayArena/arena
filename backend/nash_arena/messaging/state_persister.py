import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nash_arena.messaging.broker import MessageBroker
from nash_arena.models.session import SessionModel

logger = logging.getLogger(__name__)

PERSIST_QUEUE = "state:persist"
CACHE_TTL = 600


class StatePersister:
    def __init__(
        self,
        broker: MessageBroker,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.broker = broker
        self.session_factory = session_factory
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        logger.info("StatePersister started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("StatePersister stopped")

    async def _run(self) -> None:
        while True:
            try:
                message = await self.broker.dequeue(PERSIST_QUEUE, timeout=5)
                if message is None:
                    continue
                await self._write_to_db(message)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("StatePersister error, continuing...")

    async def _write_to_db(self, message: dict) -> None:
        session_id = message.get("session_id")
        if not session_id:
            return

        async with self.session_factory() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                logger.warning("Session %s not found for persistence", session_id)
                return

            state = message.get("state")
            if state is not None:
                row.state_json = state

            status = message.get("status")
            if status is not None:
                row.status = status

            error_message = message.get("error_message")
            if error_message is not None:
                row.error_message = error_message

            locked = message.get("locked")
            if locked is not None:
                row.locked = locked

            player_tokens = message.get("player_tokens")
            if player_tokens is not None:
                row.player_tokens_json = player_tokens

            await db.commit()
