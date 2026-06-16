import json
import os
from collections.abc import AsyncIterator
from typing import Any

from nash_arena.messaging.broker import MessageBroker

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore[assignment]


def _default_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


class RedisBroker(MessageBroker):
    def __init__(self, redis_url: str | None = None) -> None:
        if aioredis is None:
            raise RuntimeError(
                "redis is not installed. Install it with: pip install redis[hiredis]"
            )
        self.redis_url = redis_url or _default_redis_url()
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=30,
                socket_connect_timeout=10,
                retry_on_timeout=True,
            )
        return self._redis

    async def publish(self, channel: str, message: dict) -> None:
        r = await self._get_redis()
        await r.publish(channel, json.dumps(message))

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        r = await self._get_redis()
        self._pubsub = r.pubsub()
        await self._pubsub.subscribe(channel)
        try:
            async for raw in self._pubsub.listen():
                if raw["type"] != "message":
                    continue
                data = raw["data"]
                if isinstance(data, str):
                    yield json.loads(data)
        finally:
            await self._pubsub.unsubscribe(channel)
            self._pubsub = None

    async def enqueue(self, queue: str, message: dict) -> None:
        r = await self._get_redis()
        await r.rpush(queue, json.dumps(message))

    async def dequeue(self, queue: str, timeout: int = 5) -> dict | None:
        r = await self._get_redis()
        result = await r.blpop(queue, timeout=timeout)
        if result is None:
            return None
        _key, raw = result
        if isinstance(raw, str):
            return json.loads(raw)
        return None

    async def cache_set(self, key: str, value: dict, ttl: int = 300) -> None:
        r = await self._get_redis()
        await r.setex(key, ttl, json.dumps(value))

    async def cache_get(self, key: str) -> dict | None:
        r = await self._get_redis()
        raw = await r.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            return json.loads(raw)
        return None

    async def close(self) -> None:
        if self._pubsub is not None:
            await self._pubsub.close()
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def __aenter__(self) -> "RedisBroker":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
