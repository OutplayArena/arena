import asyncio
import json

import httpx
import pytest

from arena import mcp_server
from outplaylabs_arena_sdk.client import ArenaClient
from arena.auth.session_key import derive_session_key


# ── Middleware ASGI harness ──────────────────────────────────────────────────

async def _echo_context_app(scope, receive, send):
    """Minimal ASGI app: echoes whatever is in _session_ctx as JSON, or 500."""
    try:
        session_id, player, session_key = mcp_server._session_ctx.get()
        body = json.dumps({"session_id": session_id, "player": player, "session_key": session_key}).encode()
        status = 200
    except LookupError:
        body = b'{"error": "no context"}'
        status = 500
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})


_middleware_app = mcp_server._SessionKeyMiddleware(_echo_context_app)


@pytest.fixture
def middleware_client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_middleware_app), base_url="http://test")


class FakeClient:
    def __init__(self):
        self.submitted = []

    def get_state(self):
        return {"phase": "awaiting_action"}

    def submit_action(self, allocation):
        self.submitted.append(allocation)
        return {"submitted": allocation}

    def get_results(self):
        return {"winner": "A"}

    def get_observation(self, player, variant="neutral"):
        return {"system": f"You are player {player}.", "turn": "Your move.", "player_id": player, "variant": variant}

    def list_games(self):
        return [{"name": "colonelblotto"}]

    def get_game_details(self, game):
        return {"name": game}

    def get_game_metrics(self, game):
        return {"game": game, "metrics": []}

    def get_game_prompts(self, game):
        return {"game": game, "action_format": {"type": "json_array"}}

    def get_mailbox(self, player):
        return [
            {"id": "1", "sender": "A", "recipient": "all", "content": "Let's cooperate", "round": 1},
            {"id": "2", "sender": "B", "recipient": "A", "content": "I'll think about it", "round": 1},
        ]

    def send_message(self, content, recipient="all"):
        return {"status": "sent", "content": content, "recipient": recipient}


@pytest.fixture
def session_ctx_a():
    """Set _session_ctx as player A for the duration of the test."""
    session_key = derive_session_key("session-1", "A")
    token = mcp_server._session_ctx.set(("session-1", "A", session_key))
    yield session_key
    mcp_server._session_ctx.reset(token)


@pytest.fixture
def session_ctx_b():
    """Set _session_ctx as player B for the duration of the test."""
    session_key = derive_session_key("session-1", "B")
    token = mcp_server._session_ctx.set(("session-1", "B", session_key))
    yield session_key
    mcp_server._session_ctx.reset(token)


# ── _SessionKeyMiddleware tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_middleware_valid_key_sets_context(middleware_client):
    session_key = derive_session_key("sess-42", "A")
    resp = await middleware_client.get("/any", headers={"Authorization": f"Bearer {session_key}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess-42"
    assert data["player"] == "A"
    assert data["session_key"] == session_key


@pytest.mark.asyncio
async def test_middleware_missing_auth_header_returns_401(middleware_client):
    resp = await middleware_client.get("/any")
    assert resp.status_code == 401
    assert "Missing session key" in resp.json()["error"]


@pytest.mark.asyncio
async def test_middleware_wrong_token_prefix_returns_401(middleware_client):
    resp = await middleware_client.get("/any", headers={"Authorization": "Bearer nka_wrongprefix"})
    assert resp.status_code == 401
    assert "Missing session key" in resp.json()["error"]


@pytest.mark.asyncio
async def test_middleware_tampered_key_returns_401(middleware_client):
    session_key = derive_session_key("sess-42", "A")
    tampered = session_key[:-4] + "XXXX"
    resp = await middleware_client.get("/any", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
    assert "Invalid session key" in resp.json()["error"]


@pytest.mark.asyncio
async def test_middleware_health_path_returns_200(middleware_client):
    resp = await middleware_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_middleware_context_isolated_between_requests(middleware_client):
    key_a = derive_session_key("session-A", "A")
    key_b = derive_session_key("session-B", "B")

    resp_a, resp_b = await asyncio.gather(
        middleware_client.get("/any", headers={"Authorization": f"Bearer {key_a}"}),
        middleware_client.get("/any", headers={"Authorization": f"Bearer {key_b}"}),
    )

    assert resp_a.json()["session_id"] == "session-A"
    assert resp_b.json()["session_id"] == "session-B"


@pytest.mark.asyncio
async def test_middleware_resets_context_after_request(middleware_client):
    session_key = derive_session_key("sess-99", "A")
    await middleware_client.get("/any", headers={"Authorization": f"Bearer {session_key}"})
    # After the request the ContextVar in the TEST coroutine's context should be unset
    # (the middleware uses .reset(token), so the test's own context is unchanged)
    with pytest.raises((LookupError, RuntimeError)):
        mcp_server._session_ctx.get()


# ── get_session / context-var helpers ───────────────────────────────────────

def test_get_session_raises_without_context():
    with pytest.raises(RuntimeError, match="No session context"):
        mcp_server.get_session()


def test_arena_client_reads_from_context_var(session_ctx_a, monkeypatch):
    monkeypatch.setattr(mcp_server, "OUTPLAYLABS_ARENA_BASE_URL", "http://arena.test")

    client = mcp_server.arena_client()

    assert isinstance(client, ArenaClient)
    assert client.base_url == "http://arena.test"
    assert client.session_id == "session-1"
    assert client.token == session_ctx_a


def test_player_id_reads_from_context_var(session_ctx_b):
    assert mcp_server.player_id() == "B"


def test_get_game_state_calls_client(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.get_game_state() == {"phase": "awaiting_action"}


def test_submit_action_calls_client(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.submit_action([10, 0, 0]) == {"submitted": [10, 0, 0]}
    assert fake.submitted == [[10, 0, 0]]


def test_get_results_calls_client(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.get_results() == {"winner": "A"}


def test_get_observation_uses_player_from_context(session_ctx_b, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    result = mcp_server.get_observation()

    assert result["player_id"] == "B"
    assert result["variant"] == "neutral"
    assert "system" in result
    assert "turn" in result


def test_get_observation_passes_variant(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    result = mcp_server.get_observation(variant="gain_framed")

    assert result["variant"] == "gain_framed"


def test_game_directory_tools_call_client(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.list_games() == [{"name": "colonelblotto"}]
    assert mcp_server.get_game_details("colonelblotto") == {"name": "colonelblotto"}
    assert mcp_server.get_game_metrics("colonelblotto") == {"game": "colonelblotto", "metrics": []}
    assert mcp_server.get_game_prompts("colonelblotto") == {
        "game": "colonelblotto",
        "action_format": {"type": "json_array"},
    }


def test_get_mailbox_calls_client_with_player(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    result = mcp_server.get_mailbox()

    assert isinstance(result, dict)
    assert "messages" in result
    msgs = result["messages"]
    assert len(msgs) == 2
    assert msgs[0]["sender"] == "A"
    assert msgs[1]["recipient"] == "A"


def test_send_message_calls_client(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    result = mcp_server.send_message("Let's cooperate", "all")

    assert result == {"status": "sent", "content": "Let's cooperate", "recipient": "all"}


def test_send_message_with_specific_recipient(session_ctx_a, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    result = mcp_server.send_message("Private message", "B")

    assert result["recipient"] == "B"
