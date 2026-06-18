import os
os.environ["API_PREFIX"] = ""
os.environ["ENABLE_AGENT_REST_API"] = "false"
os.environ["MCP_ALLOWED_IPS"] = "127.0.0.1,testclient"

from uuid import uuid4
import importlib
import pytest
from fastapi.testclient import TestClient

import nash_arena.main
importlib.reload(nash_arena.main)
from nash_arena.main import app, get_broker  # noqa: E402
from nash_arena.db import get_db  # noqa: E402
from nash_arena.auth.dependencies import require_user, _ensure_local_user  # noqa: E402
from nash_arena.models.mcp_auth_key import McpAuthKey  # noqa: E402
from nash_arena.auth.apikey import generate_mcp_key  # noqa: E402


class FakeBroker:
    async def publish(self, channel, message):
        pass

    async def cache_get(self, key):
        return None

    async def cache_set(self, key, value, ttl=None):
        pass

    async def enqueue(self, queue, message):
        pass

    async def subscribe(self, channel):
        return
        yield


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else []


class FakeDb:
    def __init__(self):
        self._store: dict[str, object] = {}
        self._mcp_keys: dict[str, McpAuthKey] = {}
        self._last_query = ""

    async def execute(self, stmt):
        self._last_query = str(stmt)
        if "mcp_auth_keys" in self._last_query and "SELECT" in self._last_query:
            if "is_active" in self._last_query and "WHERE" in self._last_query:
                active_keys = [k for k in self._mcp_keys.values() if k.is_active]
                return FakeResult(active_keys[0] if active_keys else None)
            return FakeResult(list(self._mcp_keys.values()))
        for sid, row in self._store.items():
            if str(sid) in self._last_query:
                return FakeResult(row)
        return FakeResult(None)

    def add(self, obj):
        if isinstance(obj, McpAuthKey):
            self._mcp_keys[obj.key_hash] = obj
        else:
            self._store[str(obj.id)] = obj

    async def delete(self, obj):
        if isinstance(obj, McpAuthKey):
            self._mcp_keys.pop(obj.key_hash, None)
        else:
            self._store.pop(str(obj.id), None)

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, obj):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture(name="fake_db")
def fake_db_fixture():
    db = FakeDb()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_broker] = lambda: FakeBroker()

    async def _bypass_auth():
        return await _ensure_local_user(db)
    app.dependency_overrides[require_user] = _bypass_auth

    yield db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_broker, None)
    app.dependency_overrides.pop(require_user, None)


@pytest.fixture(autouse=True)
def disable_agent_rest_api():
    os.environ["ENABLE_AGENT_REST_API"] = "false"
    yield
    os.environ.pop("ENABLE_AGENT_REST_API", None)


def valid_payload(rounds=1):
    return {
        "game": "colonelblotto",
        "variant": "classic",
        "players": 2,
        "budget": [10, 10],
        "battlefields": [
            {"id": "A", "value": 1.0},
            {"id": "B", "value": 1.0},
            {"id": "C", "value": 1.0},
        ],
        "rounds": rounds,
        "seed": 42,
    }


def test_game_endpoint_returns_403_without_mcp_auth(fake_db):
    client = TestClient(app)

    response = client.post("/experiment", json=valid_payload())

    assert response.status_code == 403


def test_game_endpoint_returns_403_with_invalid_mcp_key(fake_db):
    client = TestClient(app)

    response = client.post(
        "/experiment",
        json=valid_payload(),
        headers={"X-MCP-Auth-Key": "invalid-key"},
    )

    assert response.status_code == 403


def test_game_endpoint_works_with_valid_mcp_key(fake_db):
    client = TestClient(app)
    full_key, key_hash, key_prefix = generate_mcp_key()
    mcp_key = McpAuthKey(
        id=uuid4(),
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="test-key",
        is_active=True,
    )
    fake_db._mcp_keys[key_hash] = mcp_key

    response = client.post(
        "/experiment",
        json=valid_payload(),
        headers={"X-MCP-Auth-Key": full_key},
    )

    assert response.status_code == 200
    assert "session_id" in response.json()


def test_game_endpoint_returns_403_with_disabled_mcp_key(fake_db):
    client = TestClient(app)
    full_key, key_hash, key_prefix = generate_mcp_key()
    mcp_key = McpAuthKey(
        id=uuid4(),
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="test-key",
        is_active=False,
    )
    fake_db._mcp_keys[key_hash] = mcp_key

    response = client.post(
        "/experiment",
        json=valid_payload(),
        headers={"X-MCP-Auth-Key": full_key},
    )

    assert response.status_code == 403


def test_state_endpoint_requires_mcp_auth(fake_db):
    client = TestClient(app)

    response = client.get("/session/nonexistent/state")

    assert response.status_code == 403


def test_observation_endpoint_requires_mcp_auth(fake_db):
    client = TestClient(app)

    response = client.get("/session/nonexistent/observation?player=A")

    assert response.status_code == 403


def test_action_endpoint_requires_mcp_auth(fake_db):
    client = TestClient(app)

    response = client.post(
        "/session/nonexistent/action",
        json={"allocation": [10, 0, 0]},
    )

    assert response.status_code == 403


def test_fail_endpoint_requires_mcp_auth(fake_db):
    client = TestClient(app)

    response = client.post(
        "/session/nonexistent/fail",
        json={"error": "test error"},
    )

    assert response.status_code == 403


def test_results_endpoint_does_not_require_mcp_auth(fake_db):
    client = TestClient(app)

    response = client.get("/session/nonexistent/results")

    assert response.status_code == 404


def test_games_endpoint_does_not_require_mcp_auth(fake_db):
    client = TestClient(app)

    response = client.get("/games")

    assert response.status_code == 200
