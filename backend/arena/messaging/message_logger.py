import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from arena.messaging.broker import MessageBroker
from arena.models.message_log import MessageLog

logger = logging.getLogger(__name__)

MESSAGE_LOG_QUEUE = "message:log"


class MessageLogger:
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
        logger.info("MessageLogger started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("MessageLogger stopped")

    async def _run(self) -> None:
        while True:
            try:
                message = await self.broker.dequeue(MESSAGE_LOG_QUEUE, timeout=5)
                if message is None:
                    continue
                await self._write_to_db(message)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("MessageLogger error, continuing...")

    async def _write_to_db(self, message: dict) -> None:
        session_id = message.get("session_id")
        if not session_id:
            return

        row = MessageLog(
            id=str(uuid.uuid4()),
            session_id=session_id,
            player=message.get("player", ""),
            round_number=message.get("round_number", 0),
            agent_id=message.get("agent_id"),
            payload=message.get("payload"),
        )

        async with self.session_factory() as db:
            db.add(row)
            await db.commit()
