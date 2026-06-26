"""Coverage tests for arena.mcp_server prompt functions and arena.messaging.redis_broker subscribe/close paths.

Targets uncovered lines:
- backend/arena/mcp_server.py: 207, 224, 235, 285-323 (game_prompt, get_game_skill, get_agent_manifest, arena intro)
- backend/arena/messaging/redis_broker.py: 34, 48-60, 74, 87, 91 (subscribe, dequeue raw, cache_get raw, close)
"""
import asyncio

import fakeredis.aioredis
import pytest

from arena import mcp_server
from arena.messaging.redis_broker import RedisBroker


# ── RedisBroker subscribe / close ───────────────────────────────────────


class TestRedisBrokerSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_yields_messages(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=True)
        broker = RedisBroker(redis_client=c)

        pubsub = c.pubsub()
        await pubsub.subscribe("ch")

        async def consume():
            messages = []
            async for msg in broker.subscribe("ch"):
                messages.append(msg)
                if len(messages) >= 1:
                    break
            return messages

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.1)
        await broker.publish("ch", {"event": "hi"})
        messages = await asyncio.wait_for(consumer, timeout=2)
        assert len(messages) == 1
        assert messages[0] == {"event": "hi"}
        await c.aclose()

    @pytest.mark.asyncio
    async def test_subscribe_skips_non_message_events(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=True)
        broker = RedisBroker(redis_client=c)
        # The pubsub 'subscribe' ack message has type != 'message'
        # and should be filtered out by our subscribe loop.
        pubsub = c.pubsub()
        await pubsub.subscribe("ch")

        async def consume():
            async for msg in broker.subscribe("ch"):
                return msg

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        await broker.publish("ch", {"data": 1})
        msg = await asyncio.wait_for(consumer, timeout=2)
        assert msg == {"data": 1}
        await c.aclose()


class TestRedisBrokerDequeueRawTypes:
    @pytest.mark.asyncio
    async def test_dequeue_returns_none_for_non_string_raw(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=False)
        broker = RedisBroker(redis_client=c)
        # Manually push bytes (non-str) to test the isinstance guard
        await c.rpush("q1", b'{"raw": "bytes"}')
        result = await broker.dequeue("q1", timeout=1)
        # decode_responses=False returns bytes; our isinstance(raw, str) check
        # will return None in that case.
        assert result is None
        await c.aclose()


class TestRedisBrokerCacheGetRawTypes:
    @pytest.mark.asyncio
    async def test_cache_get_returns_none_for_non_string(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=False)
        broker = RedisBroker(redis_client=c)
        await c.set("k1", b"not-a-string")
        result = await broker.cache_get("k1")
        assert result is None
        await c.aclose()


class TestRedisBrokerClose:
    @pytest.mark.asyncio
    async def test_close_without_pubsub(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=True)
        broker = RedisBroker(redis_client=c)
        # No pubsub, but redis is set
        await broker.cache_set("k", {"v": 1})
        await broker.close()
        assert broker._redis is None

    @pytest.mark.asyncio
    async def test_close_with_pubsub(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=True)
        broker = RedisBroker(redis_client=c)
        pubsub = c.pubsub()
        await pubsub.subscribe("ch")
        broker._pubsub = pubsub
        await broker.close()
        assert broker._redis is None
        # The middleware sets _pubsub to None in the finally block of subscribe,
        # so close() with a manually-set pubsub just closes the existing one.
        await c.aclose()

    @pytest.mark.asyncio
    async def test_lazy_redis_connection(self):
        c = fakeredis.aioredis.FakeRedis(decode_responses=True)
        broker = RedisBroker(redis_url="redis://x", redis_client=c)
        # _get_redis returns the injected client without creating a new one
        result = await broker._get_redis()
        assert result is c
        await c.aclose()


# ── mcp_server prompts and tool calls ───────────────────────────────────


class _StubArenaClient:
    def __init__(self, skill=None, prompts=None, manifest=None):
        self._skill = skill
        self._prompts = prompts
        self._manifest = manifest

    def get_game_skill(self, game):
        if self._skill is None:
            raise Exception("not found")
        return self._skill

    def get_game_prompts(self, game):
        if self._prompts is None:
            raise Exception("not found")
        return self._prompts

    def get_agent_manifest(self, game):
        return self._manifest or {}


class TestGetGameSkillTool:
    def test_get_game_skill_returns_skill(self, monkeypatch):
        skill = {"game": "blotto", "title": "Blotto", "sections": {}}
        monkeypatch.setattr(mcp_server, "arena_client", lambda: _StubArenaClient(skill=skill))
        result = mcp_server.get_game_skill("blotto")
        assert result == skill

    def test_get_game_skill_propagates_error(self, monkeypatch):
        monkeypatch.setattr(mcp_server, "arena_client", lambda: _StubArenaClient())
        with pytest.raises(Exception, match="not found"):
            mcp_server.get_game_skill("missing")


class TestGetAgentManifestTool:
    def test_get_agent_manifest_returns_manifest(self, monkeypatch):
        manifest = {"game": "blotto", "tools": []}
        monkeypatch.setattr(mcp_server, "arena_client", lambda: _StubArenaClient(manifest=manifest))
        result = mcp_server.get_agent_manifest("blotto")
        assert result == manifest

    def test_get_agent_manifest_empty(self, monkeypatch):
        monkeypatch.setattr(mcp_server, "arena_client", lambda: _StubArenaClient(manifest={}))
        result = mcp_server.get_agent_manifest("unknown")
        assert result == {}


class TestOutplaylabsArenaIntro:
    def test_intro_returns_user_message(self, monkeypatch):
        monkeypatch.setattr(mcp_server, "arena_client", lambda: _StubArenaClient())
        result = mcp_server.outplaylabs_arena_intro()
        assert isinstance(result, list)
        assert result[0]["role"] == "user"
        assert "OutplayLabs Arena" in result[0]["content"]
        assert "Authentication" in result[0]["content"]


class TestOutplaylabsArenaGamePrompt:
    def test_game_prompt_with_skill_and_prompts(self, monkeypatch):
        client = _StubArenaClient(
            skill={
                "game": "blotto",
                "title": "Colonel Blotto",
                "sections": {
                    "introduction": "Welcome",
                    "objective": "Win more battlefields",
                    "action_format": "Submit JSON array",
                    "rules": "Allocate resources",
                    "strategy_hints": "Be unpredictable",
                },
            },
            prompts={
                "system": "You are a blotto player",
                "state": "Current state: {{battlefields}}",
            },
        )
        monkeypatch.setattr(mcp_server, "arena_client", lambda: client)
        result = mcp_server.outplaylabs_arena_game_prompt("blotto")
        assert len(result) == 1
        content = result[0]["content"]
        assert "Colonel Blotto" in content
        assert "Welcome" in content
        assert "Win more battlefields" in content
        assert "System Prompt Template" in content
        assert "Turn Prompt Template" in content

    def test_game_prompt_with_no_skill_falls_back(self, monkeypatch):
        client = _StubArenaClient(skill=None, prompts={"system": "sys"})
        monkeypatch.setattr(mcp_server, "arena_client", lambda: client)
        result = mcp_server.outplaylabs_arena_game_prompt("missing")
        assert "missing Skill" in result[0]["content"]
        assert "System Prompt Template" in result[0]["content"]

    def test_game_prompt_with_no_prompts(self, monkeypatch):
        client = _StubArenaClient(
            skill={"game": "g", "title": "G", "sections": {}},
            prompts=None,
        )
        monkeypatch.setattr(mcp_server, "arena_client", lambda: client)
        result = mcp_server.outplaylabs_arena_game_prompt("g")
        content = result[0]["content"]
        # No system/turn templates
        assert "System Prompt Template" not in content
        assert "Turn Prompt Template" not in content

    def test_game_prompt_uses_strategy_notes_fallback(self, monkeypatch):
        client = _StubArenaClient(
            skill={
                "game": "pd",
                "title": "PD",
                "sections": {
                    "strategy_notes": "TFT works well",
                },
            },
            prompts={},
        )
        monkeypatch.setattr(mcp_server, "arena_client", lambda: client)
        result = mcp_server.outplaylabs_arena_game_prompt("pd")
        assert "TFT works well" in result[0]["content"]


class TestSendJsonError:
    @pytest.mark.asyncio
    async def test_send_json_error_writes_status_and_body(self):
        sent = []

        async def send(msg):
            sent.append(msg)

        await mcp_server._send_json_error(send, 400, "bad request")
        assert sent[0]["type"] == "http.response.start"
        assert sent[0]["status"] == 400
        assert sent[1]["type"] == "http.response.body"
        body = sent[1]["body"]
        assert b"bad request" in body
        assert b"error" in body


class TestSessionKeyMiddlewareHealthPath:
    @pytest.mark.asyncio
    async def test_health_path_passes_through(self):
        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = mcp_server._SessionKeyMiddleware(downstream)
        scope = {"type": "http", "path": "/health"}
        sent = []

        async def send(msg):
            sent.append(msg)

        await middleware(scope, None, send)
        assert sent[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self):
        async def downstream(scope, receive, send):
            await send({"type": "lifespan.startup"})

        middleware = mcp_server._SessionKeyMiddleware(downstream)
        scope = {"type": "lifespan"}
        sent = []

        async def send(msg):
            sent.append(msg)

        await middleware(scope, None, send)
        assert sent[0]["type"] == "lifespan.startup"
