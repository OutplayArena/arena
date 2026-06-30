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
