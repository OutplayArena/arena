"""Tests for the RedisBroker (using fakeredis to avoid a live Redis dependency)."""
import json

import fakeredis.aioredis
import pytest

from arena.messaging.redis_broker import RedisBroker


@pytest.fixture
def client():
    """A fresh in-process fakeredis client per test."""
    c = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield c
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(c.aclose())
        loop.close()
    except Exception:
        pass


@pytest.fixture
def broker(client):
    """A RedisBroker wired up to fakeredis."""
    return RedisBroker(redis_client=client)


class TestEnqueueDequeue:
    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue(self, broker):
        await broker.enqueue("q1", {"task": "do-x"})
        result = await broker.dequeue("q1", timeout=1)
        assert result == {"task": "do-x"}

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self, broker):
        result = await broker.dequeue("empty-q", timeout=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_enqueue_multiple_fifo_order(self, broker):
        await broker.enqueue("q1", {"i": 1})
        await broker.enqueue("q1", {"i": 2})
        await broker.enqueue("q1", {"i": 3})
        first = await broker.dequeue("q1", timeout=1)
        second = await broker.dequeue("q1", timeout=1)
        third = await broker.dequeue("q1", timeout=1)
        assert first == {"i": 1}
        assert second == {"i": 2}
        assert third == {"i": 3}


class TestCache:
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, broker):
        await broker.cache_set("k1", {"data": 42}, ttl=60)
        result = await broker.cache_get("k1")
        assert result == {"data": 42}

    @pytest.mark.asyncio
    async def test_cache_get_missing_returns_none(self, broker):
        result = await broker.cache_get("missing-key")
        assert result is None


class TestPublish:
    """Publish is fire-and-forget; we can verify it doesn't crash and stores the value."""

    @pytest.mark.asyncio
    async def test_publish_does_not_raise(self, broker, client):
        # Subscribe first, then publish, so the subscriber captures the message.
        pubsub = client.pubsub()
        await pubsub.subscribe("ch1")
        await broker.publish("ch1", {"event": "hello"})

        # Drain the subscribe confirmation message.
        await pubsub.get_message(timeout=1)

        # Drain the published message.
        msg = await pubsub.get_message(timeout=1)
        assert msg is not None
        assert msg["type"] == "message"
        assert json.loads(msg["data"]) == {"event": "hello"}
        await pubsub.unsubscribe("ch1")
        await pubsub.aclose()


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=True)
        async with RedisBroker(redis_client=c) as b:
            await b.publish("ch", {"x": 1})
        # After context exit, the broker's _redis is reset to None.
        assert b._redis is None
        await c.aclose()
