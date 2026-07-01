"""Tests for GDPR data-export, account-deletion, and inactivity-purge endpoints."""
import asyncio
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-gdpr" * 3)
os.environ.setdefault(
    "OUTPLAYARENA_WANDB_ENCRYPTION_KEY", secrets.token_bytes(32).hex()
)

import importlib  # noqa: E402
import pytest  # noqa: E402

import arena.main  # noqa: E402
importlib.reload(arena.main)

from arena.main import app  # noqa: E402
from arena.db import get_db  # noqa: E402
from arena.auth.dependencies import require_user, get_current_user  # noqa: E402
from arena.models.user import User  # noqa: E402
from arena.models.api_key import ApiKey  # noqa: E402
from arena.models.session import SessionModel  # noqa: E402
from arena.models.message_log import MessageLog  # noqa: E402
from arena.models.wandb_credential import WandbCredential  # noqa: E402
from arena.integrations.wandb_logger import encrypt_api_key  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


_UID = uuid.UUID("00000000-0000-0000-0000-000000000042")
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_FAKE_USER = User(
    id=_UID,
    email="alice@example.com",
    name="Alice",
    provider="github",
    provider_user_id="gh-42",
)
_FAKE_USER.created_at = _NOW
_FAKE_USER.last_login_at = _NOW


class FakeResult:
    def __init__(self, data=None):
        self._data = data if data is not None else []

    def scalar_one_or_none(self):
        if isinstance(self._data, list):
            return self._data[0] if self._data else None
        return self._data

    def scalars(self):
        return self

    def all(self):
        return self._data if isinstance(self._data, list) else []


class GdprFakeDb:
    """In-memory store for all user-linked tables, supporting SELECT and DELETE."""

    def __init__(self):
        self.users: dict[uuid.UUID, User] = {_UID: _FAKE_USER}
        self.api_keys: list[ApiKey] = []
        self.creds: dict[uuid.UUID, WandbCredential] = {}
        self.sessions: list[SessionModel] = []
        self.message_logs: list[MessageLog] = []
        self.deleted_tables: list[str] = []

    # ── SELECT dispatcher ──────────────────────────────────────────────

    async def execute(self, stmt):
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)

        is_delete = "DELETE" in compiled.upper() and "FROM" in compiled.upper()

        if is_delete:
            return await self._handle_delete(compiled)
        return self._handle_select(compiled)

    def _handle_select(self, compiled: str) -> FakeResult:
        if "wandb_credentials" in compiled:
            row = self.creds.get(_UID)
            return FakeResult(row)
        if "api_keys" in compiled:
            return FakeResult(self.api_keys)
        if "sessions" in compiled and "message_logs" not in compiled:
            return FakeResult(self.sessions)
        if "message_logs" in compiled:
            return FakeResult(self.message_logs)
        if "users" in compiled:
            # Purge-loop style query (select(User).where(last_login_at < cutoff))
            # returns the full set via .scalars().all(); single-user lookups
            # (select(User).where(id == ...)) use .scalar_one_or_none().
            if "last_login_at" in compiled:
                return FakeResult(list(self.users.values()))
            row = self.users.get(_UID)
            return FakeResult(row)
        return FakeResult([])

    async def _handle_delete(self, compiled: str) -> FakeResult:
        if "message_logs" in compiled:
            self.deleted_tables.append("message_logs")
            self.message_logs = []
        elif "api_keys" in compiled:
            self.deleted_tables.append("api_keys")
            self.api_keys = []
        elif "wandb_credentials" in compiled:
            self.deleted_tables.append("wandb_credentials")
            self.creds.pop(_UID, None)
        elif "sessions" in compiled:
            self.deleted_tables.append("sessions")
            self.sessions = []
        elif "users" in compiled:
            self.deleted_tables.append("users")
            # Mirrors the simplification used for the other tables above —
            # the WHERE clause isn't actually evaluated, so clear all rows.
            self.users = {}
        return FakeResult()

    # ── Mutations ──────────────────────────────────────────────────────

    def add(self, obj: Any) -> None:
        pass

    async def delete(self, obj: Any) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass


@pytest.fixture()
def db():
    return GdprFakeDb()


@pytest.fixture(autouse=True)
def _reset_fake_user_privacy_flag():
    """_FAKE_USER is a module-level singleton shared by reference with
    GdprFakeDb — reset mutable state between tests to avoid leakage."""
    _FAKE_USER.privacy_accepted_at = None
    yield
    _FAKE_USER.privacy_accepted_at = None


@pytest.fixture()
def client(db):
    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = lambda: _FAKE_USER
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_user, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── Data export ────────────────────────────────────────────────────────────────

def test_data_export_returns_200(client):
    resp = client.get("/settings/data-export")
    assert resp.status_code == 200


def test_data_export_includes_user_profile(client):
    resp = client.get("/settings/data-export")
    data = resp.json()
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["name"] == "Alice"
    assert str(_UID) in data["user"]["id"]


def test_data_export_has_download_filename_header(client):
    resp = client.get("/settings/data-export")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert ".json" in resp.headers.get("content-disposition", "")


def test_data_export_never_exposes_player_tokens(client, db):
    session = SessionModel(
        id="sess-1",
        config_json={"game": "blotto"},
        config_hash="abc",
        state_json={"phase": "complete"},
        player_tokens_json={"A": "secret-token-A", "B": "secret-token-B"},
        user_id=_UID,
        status="completed",
        locked=False,
    )
    session.created_at = _NOW
    session.updated_at = _NOW
    db.sessions.append(session)

    resp = client.get("/settings/data-export")
    assert "secret-token-A" not in resp.text
    assert "secret-token-B" not in resp.text
    assert "player_tokens" not in resp.json().get("sessions", [{}])[0]


def test_data_export_never_exposes_key_hash(client, db):
    key = ApiKey(
        id=uuid.uuid4(),
        user_id=_UID,
        key_hash="SHA256_HASH_NEVER_EXPOSED",
        key_prefix="oa_test_",
        name="test-key",
        is_active=True,
    )
    key.created_at = _NOW
    db.api_keys.append(key)

    resp = client.get("/settings/data-export")
    assert "SHA256_HASH_NEVER_EXPOSED" not in resp.text
    assert "key_hash" not in resp.text
    # Prefix IS safe to include
    assert "oa_test_" in resp.text


def test_data_export_never_exposes_encrypted_wandb_key(client, db):
    encrypted = encrypt_api_key("super-secret-wandb-key")
    db.creds[_UID] = WandbCredential(
        user_id=_UID,
        encrypted_api_key=encrypted,
    )
    db.creds[_UID].updated_at = _NOW

    resp = client.get("/settings/data-export")
    assert "super-secret-wandb-key" not in resp.text
    assert "encrypted_api_key" not in resp.text
    data = resp.json()
    assert data["wandb_integration"]["configured"] is True
    # Fingerprint is safe
    assert data["wandb_integration"]["key_fingerprint"] == encrypted[-8:]


def test_data_export_includes_sessions_and_logs(client, db):
    session = SessionModel(
        id="sess-2",
        config_json={"game": "blotto", "rounds": 5},
        config_hash="def",
        state_json={"phase": "complete"},
        player_tokens_json={},
        user_id=_UID,
        status="completed",
        locked=False,
    )
    session.created_at = _NOW
    session.updated_at = _NOW
    db.sessions.append(session)

    log = MessageLog(
        id="log-1",
        session_id="sess-2",
        player="A",
        round_number=1,
        agent_id="gpt-4o",
        payload={"content": "hello"},
    )
    log.created_at = _NOW
    db.message_logs.append(log)

    resp = client.get("/settings/data-export")
    data = resp.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["id"] == "sess-2"
    assert len(data["message_logs"]) == 1
    assert data["message_logs"][0]["session_id"] == "sess-2"


# ── Account deletion ───────────────────────────────────────────────────────────

def test_delete_account_returns_200(client):
    resp = client.delete("/settings/account")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_delete_account_cascades_all_tables(client, db):
    db.api_keys.append(
        ApiKey(id=uuid.uuid4(), user_id=_UID, key_hash="h", key_prefix="p", is_active=True)
    )
    encrypted = encrypt_api_key("key")
    db.creds[_UID] = WandbCredential(user_id=_UID, encrypted_api_key=encrypted)
    session = SessionModel(
        id="s1", config_json={}, config_hash="x", state_json={},
        player_tokens_json={}, user_id=_UID, status="completed", locked=False,
    )
    session.created_at = _NOW
    session.updated_at = _NOW
    db.sessions.append(session)

    client.delete("/settings/account")

    # Every table must have been touched
    assert "message_logs" in db.deleted_tables
    assert "api_keys" in db.deleted_tables
    assert "wandb_credentials" in db.deleted_tables
    assert "sessions" in db.deleted_tables
    assert "users" in db.deleted_tables


def test_delete_account_message_logs_deleted_before_sessions(client, db):
    """MessageLog has no FK cascade from sessions — must be deleted first."""
    db.sessions.append(
        SessionModel(
            id="s2", config_json={}, config_hash="x", state_json={},
            player_tokens_json={}, user_id=_UID, status="completed", locked=False,
        )
    )
    db.sessions[0].created_at = _NOW
    db.sessions[0].updated_at = _NOW

    client.delete("/settings/account")

    ml_idx = next((i for i, t in enumerate(db.deleted_tables) if t == "message_logs"), None)
    sess_idx = next((i for i, t in enumerate(db.deleted_tables) if t == "sessions"), None)
    assert ml_idx is not None and sess_idx is not None
    assert ml_idx < sess_idx, "MessageLog must be deleted before SessionModel"


# ── Privacy notice acceptance ────────────────────────────────────────────────────

def test_accept_privacy_sets_timestamp(client):
    assert _FAKE_USER.privacy_accepted_at is None

    resp = client.post("/settings/accept-privacy")

    assert resp.status_code == 200
    assert resp.json() == {"privacy_accepted": True}
    assert _FAKE_USER.privacy_accepted_at is not None


def test_accept_privacy_is_idempotent(client):
    resp1 = client.post("/settings/accept-privacy")
    first_timestamp = _FAKE_USER.privacy_accepted_at
    assert first_timestamp is not None

    resp2 = client.post("/settings/accept-privacy")

    assert resp1.status_code == resp2.status_code == 200
    # Acceptance is recorded once — a second call must not reset it.
    assert _FAKE_USER.privacy_accepted_at == first_timestamp


def test_auth_me_reflects_privacy_not_yet_accepted(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["privacy_accepted"] is False


def test_auth_me_reflects_privacy_accepted_after_acceptance(client):
    client.post("/settings/accept-privacy")
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["privacy_accepted"] is True


# ── 90-day inactivity auto-purge ─────────────────────────────────────────────────

class _FakeSessionFactory:
    """Mimics arena.db.async_session — a callable returning an async context
    manager that yields the given db object."""

    def __init__(self, db):
        self._db = db

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


def test_gdpr_purge_loop_deletes_inactive_users(monkeypatch):
    """Run a single iteration of _gdpr_purge_loop and confirm it purges a
    user whose last_login_at predates the cutoff, then exits cleanly."""
    import arena.main as main_module

    stale_user = User(
        id=uuid.UUID("00000000-0000-0000-0000-0000000000aa"),
        email="stale@example.com",
        name="Stale User",
        provider="github",
        provider_user_id="gh-stale",
    )
    stale_user.last_login_at = datetime.now(timezone.utc) - timedelta(days=200)

    db = GdprFakeDb()
    db.users = {stale_user.id: stale_user}

    monkeypatch.setattr(main_module, "_async_session_factory", _FakeSessionFactory(db))

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        raise asyncio.CancelledError()  # stop the infinite loop after one pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main_module._gdpr_purge_loop())

    assert "users" in db.deleted_tables
    assert stale_user.id not in db.users
    assert len(sleep_calls) == 1


def test_gdpr_purge_loop_continues_after_per_user_error(monkeypatch):
    """One user failing to delete must not stop the rest of the purge pass."""
    import arena.main as main_module

    async def exploding_delete(db, user_id):
        raise RuntimeError("simulated DB error")

    monkeypatch.setattr(main_module, "_delete_user_data", exploding_delete)

    stale_user = User(
        id=uuid.UUID("00000000-0000-0000-0000-0000000000bb"),
        email="stale2@example.com",
        name="Stale User 2",
        provider="github",
        provider_user_id="gh-stale-2",
    )
    stale_user.last_login_at = datetime.now(timezone.utc) - timedelta(days=200)

    db = GdprFakeDb()
    db.users = {stale_user.id: stale_user}
    monkeypatch.setattr(main_module, "_async_session_factory", _FakeSessionFactory(db))

    async def fake_sleep(seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    # The per-user RuntimeError is caught internally — the loop still
    # reaches the sleep call and raises CancelledError, not RuntimeError.
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main_module._gdpr_purge_loop())
