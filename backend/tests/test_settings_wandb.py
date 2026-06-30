"""Tests for the W&B settings API, BaseLogger abstraction, and key-leak regression."""
import os
import secrets
import uuid
from typing import Any

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-x" * 4)
# Provide a valid 32-byte hex key so encryption calls succeed.
_WANDB_KEY = secrets.token_bytes(32).hex()
os.environ.setdefault("OUTPLAYARENA_WANDB_ENCRYPTION_KEY", _WANDB_KEY)

import importlib  # noqa: E402
import pytest  # noqa: E402

import arena.main  # noqa: E402
importlib.reload(arena.main)

from arena.main import app  # noqa: E402
from arena.db import get_db  # noqa: E402
from arena.auth.dependencies import require_user  # noqa: E402
from arena.models.user import User  # noqa: E402
from arena.models.wandb_credential import WandbCredential  # noqa: E402
from arena.integrations.wandb_logger import encrypt_api_key  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


_FAKE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
_FAKE_USER = User(
    id=_FAKE_USER_ID,
    email="test@example.com",
    name="Tester",
    provider="github",
    provider_user_id="gh-99",
)


class FakeResult:
    def __init__(self, data=None):
        self._data = data

    def scalar_one_or_none(self):
        return self._data

    def scalars(self):
        return self

    def all(self):
        return self._data if isinstance(self._data, list) else []


class FakeDb:
    """Minimal in-memory store for WandbCredential rows."""

    def __init__(self):
        self._creds: dict[uuid.UUID, WandbCredential] = {}

    async def execute(self, stmt):
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)

        if "wandb_credentials" in compiled:
            row = self._creds.get(_FAKE_USER_ID)
            return FakeResult(row)
        return FakeResult(None)

    def add(self, obj: Any):
        if isinstance(obj, WandbCredential):
            self._creds[obj.user_id] = obj

    async def delete(self, obj: Any):
        if isinstance(obj, WandbCredential):
            self._creds.pop(obj.user_id, None)

    async def commit(self):
        pass

    async def refresh(self, obj: Any):
        pass


@pytest.fixture()
def db():
    return FakeDb()


@pytest.fixture()
def client(db):
    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = lambda: _FAKE_USER
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_user, None)


# ── BaseLogger ────────────────────────────────────────────────────────────────

def test_base_logger_is_abstract():
    from arena.integrations.base_logger import BaseLogger
    with pytest.raises(TypeError):
        BaseLogger()  # type: ignore[abstract]


def test_wandb_game_logger_implements_base_logger():
    from arena.integrations.base_logger import BaseLogger
    from arena.integrations.wandb_logger import WandbGameLogger
    assert issubclass(WandbGameLogger, BaseLogger)


def test_wandb_game_logger_includes_agents_in_full_config():
    from arena.experiment_config import WandbConfig
    from arena.integrations.wandb_logger import WandbGameLogger
    key = secrets.token_bytes(32)
    encrypted = encrypt_api_key("fake-key", key=key)
    cfg = WandbConfig(api_key="fake-key", project="test-project")
    agents = {"A": "gpt-4o", "B": "claude-opus"}

    logger = WandbGameLogger(
        wandb_config=cfg,
        game_config={"game": "blotto", "rounds": 3},
        encrypted_api_key=encrypted,
        agents=agents,
    )

    full = logger._full_config_dict()
    assert full["agents"] == agents
    assert full["game"] == "blotto"


def test_wandb_game_logger_full_config_without_agents():
    from arena.experiment_config import WandbConfig
    from arena.integrations.wandb_logger import WandbGameLogger
    key = secrets.token_bytes(32)
    encrypted = encrypt_api_key("fake-key", key=key)
    cfg = WandbConfig(api_key="fake-key", project="test-project")

    logger = WandbGameLogger(
        wandb_config=cfg,
        game_config={"game": "blotto"},
        encrypted_api_key=encrypted,
    )

    assert logger._full_config_dict()["agents"] == {}


# ── Settings endpoints ────────────────────────────────────────────────────────

def test_wandb_key_not_configured_by_default(client):
    resp = client.get("/settings/wandb-key")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["updated_at"] is None
    assert data["key_fingerprint"] is None


def test_save_wandb_key(client, db):
    resp = client.put("/settings/wandb-key", json={"api_key": "my-secret-key"})
    assert resp.status_code == 200
    assert resp.json()["configured"] is True
    # Row must exist in the fake store
    assert _FAKE_USER_ID in db._creds


def test_get_status_after_save(client, db):
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID,
        encrypted_api_key=encrypt_api_key("secret"),
    )
    resp = client.get("/settings/wandb-key")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    # The key must NEVER appear in any response field.
    assert "secret" not in resp.text
    assert "api_key" not in data
    # Fingerprint — last 8 chars of the encrypted blob, never the plaintext.
    assert data["key_fingerprint"] is not None
    assert len(data["key_fingerprint"]) == 8
    assert "secret" not in data["key_fingerprint"]


def test_delete_wandb_key(client, db):
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID,
        encrypted_api_key=encrypt_api_key("secret"),
    )
    resp = client.delete("/settings/wandb-key")
    assert resp.status_code == 200
    assert _FAKE_USER_ID not in db._creds


def test_delete_wandb_key_when_not_configured_returns_404(client):
    resp = client.delete("/settings/wandb-key")
    assert resp.status_code == 404


def test_entities_endpoint_returns_404_when_no_key(client):
    resp = client.get("/settings/wandb-key/entities")
    assert resp.status_code == 404


def test_save_wandb_key_rejects_empty_key(client):
    resp = client.put("/settings/wandb-key", json={"api_key": ""})
    assert resp.status_code == 400


# ── Key-leak regression ───────────────────────────────────────────────────────

def test_get_status_never_exposes_api_key(client, db):
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID,
        encrypted_api_key=encrypt_api_key("super-secret-wandb-key"),
    )
    resp = client.get("/settings/wandb-key")
    assert "super-secret-wandb-key" not in resp.text
    assert "encrypted_api_key" not in resp.text


def test_inline_api_key_in_wandb_block_is_rejected(client):
    """A request that sends wandb.api_key in the payload must be rejected."""
    resp = client.post("/experiment", json={
        "game": "blotto",
        "rounds": 1,
        "wandb": {"api_key": "should-be-rejected", "project": "test"},
    })
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "api_key" in detail or "settings" in detail


# ── /settings/wandb-key/entities ────────────────────────────────────────────────

class _FakeViewer:
    def __init__(self, entity, teams):
        self.entity = entity
        self.teams = teams


class _FakeWandbApi:
    def __init__(self, api_key=None):
        self.api_key = api_key

    @property
    def viewer(self):
        return _FakeViewer(entity="alice", teams=["alice", "lab-team", "another-team"])


def test_entities_endpoint_success(client, db, monkeypatch):
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID, encrypted_api_key=encrypt_api_key("real-key")
    )
    monkeypatch.setattr("wandb.Api", _FakeWandbApi)

    resp = client.get("/settings/wandb-key/entities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["personal_entity"] == "alice"
    # Personal entity de-duplicated, order preserved
    assert data["entities"] == ["alice", "lab-team", "another-team"]
    assert "real-key" not in resp.text


def test_entities_endpoint_decrypt_failure_returns_500(client, db):
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID, encrypted_api_key="not-valid-base64!!"
    )
    resp = client.get("/settings/wandb-key/entities")
    assert resp.status_code == 500


def test_entities_endpoint_wandb_api_failure_returns_502(client, db, monkeypatch):
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID, encrypted_api_key=encrypt_api_key("real-key")
    )

    class ExplodingApi:
        def __init__(self, api_key=None):
            raise ConnectionError("simulated network failure")

    monkeypatch.setattr("wandb.Api", ExplodingApi)

    resp = client.get("/settings/wandb-key/entities")
    assert resp.status_code == 502
    assert "real-key" not in resp.text


# ── create_experiment W&B wiring ─────────────────────────────────────────────────

class _NoOpWandbLogger:
    """Records construction args without touching the network."""
    instances: list = []

    def __init__(self, wandb_config, game_config, encrypted_api_key, agents=None):
        self.wandb_config = wandb_config
        self.game_config = game_config
        self.encrypted_api_key = encrypted_api_key
        self.agents = agents
        _NoOpWandbLogger.instances.append(self)

    def start(self):
        return self


@pytest.fixture(autouse=True)
def _reset_wandb_logger_instances():
    _NoOpWandbLogger.instances = []
    yield


def _experiment_payload(**overrides):
    payload = {
        "game": "prisonersdilemma",
        "rounds": 1,
        "players": 2,
        "agents": {"A": "agent-a", "B": "agent-b"},
    }
    payload.update(overrides)
    return payload


def test_create_experiment_with_wandb_logging_resolves_stored_key(client, db, monkeypatch):
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID, encrypted_api_key=encrypt_api_key("real-wandb-key")
    )
    monkeypatch.setattr("arena.session.WandbGameLogger", _NoOpWandbLogger)

    resp = client.post("/experiment", json=_experiment_payload(
        wandb_logging=True, wandb_project="my-proj", wandb_entity="my-team",
    ))

    assert resp.status_code == 200
    assert len(_NoOpWandbLogger.instances) == 1
    logged = _NoOpWandbLogger.instances[0]
    assert logged.wandb_config.project == "my-proj"
    assert logged.wandb_config.entity == "my-team"
    assert logged.agents == {"A": "agent-a", "B": "agent-b"}
    # Real key never appears in the response
    assert "real-wandb-key" not in resp.text


def test_create_experiment_wandb_logging_without_stored_key_still_succeeds(client, monkeypatch):
    """No credential configured — experiment must still run, just without W&B."""
    monkeypatch.setattr("arena.session.WandbGameLogger", _NoOpWandbLogger)

    resp = client.post("/experiment", json=_experiment_payload(wandb_logging=True))

    assert resp.status_code == 200
    assert len(_NoOpWandbLogger.instances) == 0


def test_create_experiment_wandb_logging_with_broken_key_still_succeeds(client, db, monkeypatch):
    """A corrupted stored credential must not fail the experiment."""
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID, encrypted_api_key="not-valid-base64!!"
    )
    monkeypatch.setattr("arena.session.WandbGameLogger", _NoOpWandbLogger)

    resp = client.post("/experiment", json=_experiment_payload(wandb_logging=True))

    assert resp.status_code == 200
    assert len(_NoOpWandbLogger.instances) == 0


def test_create_experiment_without_wandb_logging_flag_skips_wandb_entirely(client, db, monkeypatch):
    """Even with a stored key, omitting wandb_logging must not start a logger."""
    db._creds[_FAKE_USER_ID] = WandbCredential(
        user_id=_FAKE_USER_ID, encrypted_api_key=encrypt_api_key("real-wandb-key")
    )
    monkeypatch.setattr("arena.session.WandbGameLogger", _NoOpWandbLogger)

    resp = client.post("/experiment", json=_experiment_payload())

    assert resp.status_code == 200
    assert len(_NoOpWandbLogger.instances) == 0
