"""Tests for the 'config' field echoed in creation_response, public_state, and get_results.

The SDK's forthcoming BaseAgent reads `config` from the first backend response it gets
(see PR #37 plan). These tests pin the contract:

  - POST /experiment returns a body with a `config` key equal to the sent config.
  - GET  /session/{id}/state returns a body with a `config` key.
  - GET  /session/{id}/results returns a body with a `config` key.

And on the engine side:

  - Each game's public_state() includes a `config` key in its return dict.
  - session.creation_response() includes the full config dict.
"""
from __future__ import annotations

import os

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")

import importlib
import pytest
from fastapi.testclient import TestClient

import arena.main
importlib.reload(arena.main)
from arena.main import app, get_broker  # noqa: E402
from arena.db import get_db  # noqa: E402
from arena.auth.dependencies import require_user, _ensure_local_user  # noqa: E402
from arena.session import GameSession  # noqa: E402


# ── Fakes — kept in lockstep with test_fastapi_app.py / test_mailbox.py ──────

class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        if self._value is None:
            raise Exception("No row found")
        return self._value


class _FakeBroker:
    def __init__(self, db=None):
        self._db = db
        self._cache: dict = {}

    async def publish(self, channel, message):
        pass

    async def cache_get(self, key):
        return self._cache.get(key)

    async def cache_set(self, key, value, ttl=None):
        self._cache[key] = value

    async def enqueue(self, queue, message):
        if queue == "state:persist" and self._db:
            session_id = message.get("session_id")
            if session_id and session_id in self._db._store:
                row = self._db._store[session_id]
                row.state_json = message.get("state", row.state_json)
                row.status = message.get("status", row.status)
                row.error_message = message.get("error_message")
                row.locked = message.get("locked", row.locked)

    async def subscribe(self, channel):
        if False:
            yield


class _FakeDb:
    def __init__(self):
        self._store: dict = {}

    async def execute(self, stmt):
        from arena.auth.dependencies import LOCAL_USER_ID
        from arena.models.user import User
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        if "users" in compiled and "local" in compiled:
            user = User(id=LOCAL_USER_ID)
            user.id = LOCAL_USER_ID
            return _FakeResult(user)
        for sid, row in self._store.items():
            if str(sid) in compiled:
                return _FakeResult(row)
        return _FakeResult(None)

    def add(self, obj):
        self._store[str(obj.id)] = obj

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, obj):
        stored = self._store.get(str(obj.id))
        if stored is not None:
            for key in obj.__dict__:
                if not key.startswith("_"):
                    setattr(obj, key, getattr(stored, key, getattr(obj, key)))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def fake_db():
    db = _FakeDb()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_broker] = lambda: _FakeBroker(db)

    async def _bypass_auth():
        return await _ensure_local_user(db)
    app.dependency_overrides[require_user] = _bypass_auth

    yield db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_broker, None)
    app.dependency_overrides.pop(require_user, None)


@pytest.fixture(autouse=True)
def enable_agent_rest_api():
    os.environ["ENABLE_AGENT_REST_API"] = "true"
    yield


def _cb_payload(rounds=1, seed=42):
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
        "seed": seed,
    }


# ── creation_response ────────────────────────────────────────────────────────

def test_creation_response_includes_config(fake_db):
    """POST /experiment returns a body with a 'config' key."""
    client = TestClient(app)
    response = client.post("/experiment", json=_cb_payload(rounds=2))

    assert response.status_code == 200, response.text
    data = response.json()
    assert "config" in data, "creation_response must include 'config' for the SDK to auto-consume the seed"
    assert data["config"]["game"] == "colonelblotto"
    assert data["config"]["seed"] == 42
    assert data["config"]["rounds"] == 2
    assert data["config"]["budget"] == [10, 10]
    assert len(data["config"]["battlefields"]) == 3


def test_creation_response_session_level_config_equals_engine_config():
    """The config echoed in creation_response equals config.to_dict()."""
    from games.core.colonelblotto.config import (
        BattlefieldConfig,
        ColonelBlottoExperimentConfig,
    )

    cfg = ColonelBlottoExperimentConfig(
        game="colonelblotto",
        variant="classic",
        players=2,
        budget=[10, 10],
        battlefields=[
            BattlefieldConfig(id="A", value=1.0),
            BattlefieldConfig(id="B", value=1.0),
            BattlefieldConfig(id="C", value=1.0),
        ],
        rounds=1,
        seed=7,
    )
    session = GameSession.create(cfg)
    response = session.creation_response()

    assert response["config"] == cfg.to_dict()


# ── public_state ─────────────────────────────────────────────────────────────

def test_public_state_includes_config(fake_db):
    """GET /session/{id}/state returns a body with a 'config' key."""
    client = TestClient(app)
    created = client.post("/experiment", json=_cb_payload()).json()
    session_id = created["session_id"]

    response = client.get(f"/session/{session_id}/state")
    assert response.status_code == 200, response.text
    state = response.json()
    assert "config" in state, "public_state must include 'config'"
    assert state["config"]["game"] == "colonelblotto"
    assert state["config"]["seed"] == 42
    assert len(state["config"]["battlefields"]) == 3


def test_submit_action_response_includes_config(fake_db):
    """POST /session/{id}/action returns the updated public_state, which must include 'config'."""
    client = TestClient(app)
    created = client.post("/experiment", json=_cb_payload(rounds=1)).json()
    session_id = created["session_id"]
    token_a = created["player_tokens"]["A"]

    response = client.post(
        f"/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [10, 0, 0]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "config" in body
    assert body["config"]["game"] == "colonelblotto"


# ── get_results ──────────────────────────────────────────────────────────────

def test_results_includes_config(fake_db):
    """GET /session/{id}/results returns a body with a 'config' key once the game is complete."""
    client = TestClient(app)
    created = client.post("/experiment", json=_cb_payload(rounds=1)).json()
    session_id = created["session_id"]
    token_a = created["player_tokens"]["A"]
    token_b = created["player_tokens"]["B"]

    client.post(
        f"/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [10, 0, 0]},
    )
    client.post(
        f"/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"allocation": [0, 5, 5]},
    )

    response = client.get(f"/session/{session_id}/results")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "config" in body, "get_results must include 'config'"
    assert body["config"]["game"] == "colonelblotto"
    assert body["config"]["seed"] == 42
    assert body["config"]["rounds"] == 1


# ── Per-game public_state() contract ─────────────────────────────────────────
# Each game engine's public_state() must include a 'config' key. We exercise
# the engine directly (no HTTP) to keep the test fast and to cover all 10 games.

GAME_CONFIG_BUILDERS = {
    "colonelblotto": lambda: {
        "game": "colonelblotto",
        "variant": "classic",
        "players": 2,
        "budget": [10, 10],
        "battlefields": [
            {"id": "A", "value": 1.0},
            {"id": "B", "value": 1.0},
            {"id": "C", "value": 1.0},
        ],
        "rounds": 1,
        "seed": 1,
    },
    "ultimatum": lambda: {
        "game": "ultimatum",
        "players": 2,
        "rounds": 1,
        "total": 100.0,
        "min_offer": 1.0,
        "seed": 2,
    },
    "prisonersdilemma": lambda: {
        "game": "prisonersdilemma",
        "variant": "classic",
        "players": 2,
        "rounds": 1,
        "noise": 0.0,
        "seed": 3,
    },
    "rock_paper_scissors": lambda: {
        "game": "rock_paper_scissors",
        "players": 2,
        "rounds": 1,
        "seed": 4,
    },
    "battle_of_the_sexes": lambda: {
        "game": "battle_of_the_sexes",
        "players": 2,
        "rounds": 1,
        "seed": 5,
    },
    "stag_hunt": lambda: {
        "game": "stag_hunt",
        "variant": "classic",
        "players": 2,
        "rounds": 1,
        "noise": 0.0,
        "seed": 6,
    },
    "centipede": lambda: {
        "game": "centipede",
        "players": 2,
        "max_steps": 3,
        "seed": 7,
    },
    "cournot_duopoly": lambda: {
        "game": "cournot_duopoly",
        "players": 2,
        "rounds": 1,
        "seed": 8,
    },
    "public_goods": lambda: {
        "game": "public_goods",
        "variant": "classic",
        "players": 3,
        "rounds": 1,
        "endowment": 20.0,
        "multiplier": 1.5,
        "seed": 9,
    },
    "texas_hold_em": lambda: {
        "game": "texas_hold_em",
        "rounds": 1,
        "seed": 10,
    },
}


@pytest.mark.parametrize("game", sorted(GAME_CONFIG_BUILDERS.keys()))
def test_every_game_public_state_includes_config(game):
    """Every per-game engine's public_state() must include a 'config' key."""
    from arena.game_registry import GameRegistry
    from arena.game_engine import GameEngine

    payload = GAME_CONFIG_BUILDERS[game]()
    registry = GameRegistry()
    config = registry.config_from_request(payload)
    engine = registry.game_from_config(config)
    assert isinstance(engine, GameEngine)

    state = engine.initial_state()
    public = engine.public_state(state, config, "sess-1", "hash-1")

    assert "config" in public, f"{game}.public_state() must include 'config'"
    assert public["config"] == config.to_dict(), (
        f"{game}.public_state()['config'] must equal config.to_dict()"
    )
    assert public["config"].get("seed") == payload["seed"], (
        f"{game} config should preserve the user-supplied seed"
    )
