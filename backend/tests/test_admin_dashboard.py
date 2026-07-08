"""Tests for the admin dashboard (#116): require_admin gate, masked
emails, /api/admin/* endpoints, site-config admin_enabled flag, and the
login_enabled toggle enforcement on OAuth login redirects.
"""
import os
import uuid

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-ad" * 4)

import importlib  # noqa: E402
import pytest  # noqa: E402

import arena.main  # noqa: E402
importlib.reload(arena.main)

from arena.main import app, _mask_email  # noqa: E402
from arena.settings import get_settings  # noqa: E402
from arena.auth.dependencies import require_admin, _user_is_admin, _is_admin_enabled  # noqa: E402
from arena.models.user import User  # noqa: E402
from arena.models.platform_setting import PlatformSetting  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402


# ── masked email helper ────────────────────────────────────────────────────


class TestMaskEmail:
    def test_mask_standard_email(self):
        masked = _mask_email("alice@example.com")
        assert masked.startswith("a***@***")
        assert "@" in masked
        assert "alice" not in masked

    def test_mask_preserves_tld(self):
        masked = _mask_email("bob@arena.io")
        assert "io" in masked

    def test_mask_short_name(self):
        masked = _mask_email("x@y.io")
        assert "@" in masked
        assert "x" in masked

    def test_mask_returns_as_is_on_garbage(self):
        assert _mask_email("not-an-email") == "not-an-email"
        assert _mask_email("") == ""
        assert _mask_email("a@") == "a@"


# ── require_admin gate ────────────────────────────────────────────────────


class FakeResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return list(self._value)
        return [self._value] if self._value is not None else []


class FakeAdminDb:
    """Stores users + platform_settings; minimal admin-query support."""

    def __init__(self, users=None, settings=None):
        self.users = users or {}
        self.settings = settings if settings is not None else {}
        self.added = []

    async def execute(self, stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        if "platform_settings" in compiled and "WHERE" in compiled.upper():
            for key, val in self.settings.items():
                if f"'{key}'" in compiled:
                    return FakeResult(PlatformSetting(key=key, value=val))
            return FakeResult(None)
        if "FROM users" in compiled or "FROM sessions" in "FROM sessions":
            # Return matching user by id when looking up.
            for uid, u in self.users.items():
                if str(uid) in compiled:
                    return FakeResult(u)
            return FakeResult(None)
        return FakeResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestRequireAdminGate:
    @pytest.mark.asyncio
    async def test_rejects_when_dashboard_disabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "false")
        get_settings.cache_clear()
        db = FakeAdminDb()
        with pytest.raises(Exception) as exc_info:
            await require_admin(authorization="Bearer x", db=db)
        assert "disabled" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_rejects_non_admin_user(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "true")
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        get_settings.cache_clear()

        uid = uuid.uuid4()
        non_admin = User(
            id=uid,
            email="joe@example.com",
            name="Joe",
            provider="github",
            provider_user_id="joe",
        )
        non_admin.is_admin = False

        # Patch require_user (or its internals) by injecting a valid bearer
        # pointing to our fake user. We monkeypatch the OAuth/JWT path.
        async def _fake_get_current_user(authorization, db):
            return non_admin

        import arena.auth.dependencies as dep
        monkeypatch.setattr(dep, "get_current_user", _fake_get_current_user)
        monkeypatch.setattr(
            "arena.auth.dependencies._providers_configured", lambda: True
        )

        db = FakeAdminDb(users={uid: non_admin})
        with pytest.raises(Exception) as exc_info:
            await require_admin(authorization="Bearer x", db=db)
        assert "admin" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_allows_admin_via_db_flag(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "true")
        get_settings.cache_clear()

        uid = uuid.uuid4()
        admin = User(
            id=uid,
            email="root@example.com",
            name="Root",
            provider="github",
            provider_user_id="root",
        )
        admin.is_admin = True

        async def _fake_get_current_user(authorization, db):
            return admin

        import arena.auth.dependencies as dep
        monkeypatch.setattr(dep, "get_current_user", _fake_get_current_user)
        monkeypatch.setattr(
            "arena.auth.dependencies._providers_configured", lambda: True
        )

        db = FakeAdminDb(users={uid: admin})
        result = await require_admin(authorization="Bearer x", db=db)
        assert result.id == uid

    @pytest.mark.asyncio
    async def test_allows_admin_via_env_allowlist(self, monkeypatch):
        uid = uuid.uuid4()
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "true")
        monkeypatch.setenv("ADMIN_USER_IDS", str(uid))
        get_settings.cache_clear()

        admin = User(
            id=uid,
            email="ops@example.com",
            name="Ops",
            provider="github",
            provider_user_id="ops",
        )
        admin.is_admin = False  # env allowlist is the only admin signal

        async def _fake_get_current_user(authorization, db):
            return admin

        import arena.auth.dependencies as dep
        monkeypatch.setattr(dep, "get_current_user", _fake_get_current_user)
        monkeypatch.setattr(
            "arena.auth.dependencies._providers_configured", lambda: True
        )

        db = FakeAdminDb(users={uid: admin})
        result = await require_admin(authorization="Bearer x", db=db)
        assert result.id == uid


# ── /api/admin/* endpoints (integration via TestClient) ─────────────────


class _Broker:
    async def publish(self, channel, message):
        pass


def _seed_admin_client(monkeypatch, db, admin_user):
    """Wire require_admin → admin_user and get_db → db on the app."""
    async def _db_factory():
        yield db

    def _need_admin(authorization=None, db=None):
        return admin_user

    app.dependency_overrides[arena.main.get_db] = _db_factory
    app.dependency_overrides[require_admin] = _need_admin
    app.dependency_overrides[arena.main.get_broker] = lambda: _Broker()
    return TestClient(app)


def _cleanup_overrides():
    app.dependency_overrides.clear()


class TestAdminUsersEndpoint:
    def test_returns_users_with_masked_emails(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(
            id=uid,
            email="admin@example.com",
            name="Admin",
            provider="github",
            provider_user_id="admin",
        )
        admin.is_admin = True
        admin.username = "admin"

        # The endpoint queries `select(User).order_by(...)`. Reuse FakeAdminDb
        # which returns scalars for FROM users.
        class Db(FakeAdminDb):
            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                if "FROM users" in compiled:
                    return FakeResult(list(self.users.values()))
                return await super().execute(stmt)

            def add(self, obj):
                pass

            async def commit(self):
                pass

            async def refresh(self, obj):
                pass

        db = Db(users={uid: admin})
        client = _seed_admin_client(monkeypatch, db, admin)
        try:
            resp = client.get("/admin/users")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert isinstance(data["users"], list)
            assert any(u["username"] == "admin" for u in data["users"])
            # Masked email doesn't contain the full address.
            assert "admin@example.com" not in resp.text
            assert all("email_masked" in u for u in data["users"])
        finally:
            _cleanup_overrides()


class TestAdminStatsEndpoint:
    def test_returns_all_counters(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(
            id=uid,
            email="admin@example.com",
            name="Admin",
            provider="github",
            provider_user_id="admin",
        )
        admin.is_admin = True

        class Db(FakeAdminDb):
            def __init__(self, users=None):
                super().__init__(users=users)
                self.counts = {
                    "running": 3,
                    "ready": 2,
                    "queued": 1,
                    "failed": 4,
                    "completed": 7,
                }
                self.wandb_count = 5

            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                low = compiled.lower()
                if "count(" in low and "sessions" in low:
                    for status, n in self.counts.items():
                        if status in compiled:
                            return FakeResult(n)
                    return FakeResult(0)
                if "count(" in low and "wandb_credentials" in low:
                    return FakeResult(self.wandb_count)
                if "platform_settings" in compiled and "WHERE" in compiled.upper():
                    for key, val in self.settings.items():
                        if f"'{key}'" in compiled:
                            return FakeResult(PlatformSetting(key=key, value=str(val)))
                    return FakeResult(None)
                if "pg_database_size" in low:
                    return FakeResult(123456)
                return FakeResult(None)

        db = Db(users={uid: admin})
        db.settings = {"login_enabled": "true"}
        client = _seed_admin_client(monkeypatch, db, admin)
        try:
            resp = client.get("/admin/stats")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["sessions_running"] == 3
            assert data["sessions_ready"] == 2
            assert data["sessions_queued"] == 1
            assert data["sessions_failed"] == 4
            assert data["sessions_completed"] == 7
            assert data["wandb_users"] == 5
            assert data["login_enabled"] is True
            assert data["db_size_bytes"] == 123456
            assert data["backup"]["status"] == "not_configured"
        finally:
            _cleanup_overrides()


class TestAdminSettingsEndpoint:
    def test_get_returns_current_settings(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(id=uid, email="a@b.io", name="A", provider="github", provider_user_id="a")
        admin.is_admin = True

        db = FakeAdminDb(
            users={uid: admin},
            settings={
                "max_concurrent_sessions": "7",
                "max_concurrent_sessions_per_user": "2",
                "login_enabled": "true",
            },
        )
        client = _seed_admin_client(monkeypatch, db, admin)
        try:
            resp = client.get("/admin/settings")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["max_concurrent_sessions"] == 7
            assert data["max_concurrent_sessions_per_user"] == 2
            assert data["login_enabled"] is True
        finally:
            _cleanup_overrides()

    def test_put_updates_provided_keys_only(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(id=uid, email="a@b.io", name="A", provider="github", provider_user_id="a")
        admin.is_admin = True

        captured = {}

        class Db(FakeAdminDb):
            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                if "platform_settings" in compiled and "WHERE" in compiled.upper():
                    for key, val in self.settings.items():
                        if f"'{key}'" in compiled:
                            return FakeResult(PlatformSetting(key=key, value=str(val)))
                    return FakeResult(None)
                return FakeResult(None)

        db = Db(users={uid: admin}, settings={"login_enabled": "true", "max_concurrent_sessions": "5", "max_concurrent_sessions_per_user": "1"})

        # Patch the set helper to record writes.
        import arena.platform_settings as ps
        async def _fake_set(key, value, _db, updated_by=None):
            captured[key] = value
            return str(value)
        monkeypatch.setattr(ps, "set_platform_setting", _fake_set)
        # The main module already bound the name at import time, so rebind there too.
        import arena.main as _m
        monkeypatch.setattr(
            _m, "set_platform_setting", _fake_set, raising=False
        )
        # main.py imports it lazily inside the handler — rebind the lazy import.
        #import arena.platform_settings as _ps

        async def _fake_getset(key, _db, cast=str):
            return cast(str(db.settings.get(key, "")))
        monkeypatch.setattr(ps, "get_platform_setting", _fake_getset)

        client = _seed_admin_client(monkeypatch, db, admin)
        try:
            resp = client.put("/admin/settings", json={"max_concurrent_sessions": "9", "bad_key": "x"})
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "max_concurrent_sessions" in data
            assert "bad_key" not in data
            assert captured.get("max_concurrent_sessions") == "9"
        finally:
            _cleanup_overrides()


class TestSiteConfigAdminFlag:
    def test_site_config_includes_admin_dashboard_enabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "true")
        get_settings.cache_clear()
        client = TestClient(app)
        resp = client.get("/site-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "admin_dashboard_enabled" in data
        assert data["admin_dashboard_enabled"] is True

    def test_site_config_admin_flag_defaults_false(self, monkeypatch):
        monkeypatch.delenv("ENABLE_ADMIN_DASHBOARD", raising=False)
        get_settings.cache_clear()
        client = TestClient(app)
        data = client.get("/site-config").json()
        assert data["admin_dashboard_enabled"] is False


class TestUserIsAdmin:
    def test_db_flag_grants_admin(self):
        u = User(id=uuid.uuid4(), email="x@y.io", name="X", provider="github", provider_user_id="x")
        u.is_admin = True
        assert _user_is_admin(u) is True

    def test_default_user_is_not_admin(self):
        u = User(id=uuid.uuid4(), email="x@y.io", name="X", provider="github", provider_user_id="x")
        u.is_admin = False
        assert _user_is_admin(u) is False

    def test_env_allowlist_grants_admin(self, monkeypatch):
        uid = uuid.uuid4()
        monkeypatch.setenv("ADMIN_USER_IDS", str(uid))
        get_settings.cache_clear()
        u = User(id=uid, email="x@y.io", name="X", provider="github", provider_user_id="x")
        u.is_admin = False
        assert _user_is_admin(u) is True


class TestIsAdminEnabled:
    def test_reflects_env_var(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "true")
        get_settings.cache_clear()
        assert _is_admin_enabled() is True
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "false")
        get_settings.cache_clear()
        assert _is_admin_enabled() is False


# ── /admin/sessions endpoint (#116) ──────────────────────────────────────


class _FakeSessionRow:
    def __init__(self, sid, status="running", game="test_game",
                 user_id=None, is_public=False, created_at=None):
        import datetime
        self.id = sid
        self.status = status
        self.config_json = {"game": game}
        self.user_id = user_id
        self.is_public = is_public
        self.created_at = created_at or datetime.datetime.now(datetime.timezone.utc)


class TestAdminSessionsEndpoint:
    def test_returns_sessions_with_total(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(id=uid, email="a@b.io", name="A", provider="github", provider_user_id="a")
        admin.is_admin = True

        sessions = [
            _FakeSessionRow("s1", status="running", game="blotto", user_id=uid, is_public=True),
            _FakeSessionRow("s2", status="ready", game="prisoner", user_id=None, is_public=False),
        ]

        class Db(FakeAdminDb):
            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                low = compiled.lower()
                if "count(" in low and "sessions" in low:
                    return FakeResult(len(sessions))
                if "from sessions" in low:
                    return FakeResult(sessions)
                return await super().execute(stmt)

        db = Db(users={uid: admin})
        client = _seed_admin_client(monkeypatch, db, admin)
        try:
            resp = client.get("/admin/sessions?limit=10&offset=0")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["total"] == 2
            assert len(data["sessions"]) == 2
            assert data["sessions"][0]["game"] == "blotto"
            assert data["sessions"][0]["is_public"] is True
        finally:
            _cleanup_overrides()


# ── /admin/errors endpoint (#116) ────────────────────────────────────────


class _FakeErrorLog:
    def __init__(self, eid, method="GET", path="/api/test",
                 exception_type="ValueError", message="boom",
                 client_ip="127.0.0.1", user_agent="test-agent", created_at=None):
        import datetime
        self.id = eid
        self.method = method
        self.path = path
        self.exception_type = exception_type
        self.message = message
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.created_at = created_at or datetime.datetime.now(datetime.timezone.utc)


class TestAdminErrorsEndpoint:
    def test_returns_recent_errors(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(id=uid, email="a@b.io", name="A", provider="github", provider_user_id="a")
        admin.is_admin = True

        errors = [
            _FakeErrorLog(uuid.uuid4(), method="POST", path="/api/experiment",
                          exception_type="RuntimeError", message="crash"),
            _FakeErrorLog(uuid.uuid4(), method="GET", path="/api/leaderboard",
                          exception_type="KeyError", message="missing key"),
        ]

        class Db(FakeAdminDb):
            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                low = compiled.lower()
                if "error_logs" in low:
                    return FakeResult(errors)
                return await super().execute(stmt)

        db = Db(users={uid: admin})
        client = _seed_admin_client(monkeypatch, db, admin)
        try:
            resp = client.get("/admin/errors?limit=50")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert len(data["errors"]) == 2
            assert data["errors"][0]["exception_type"] == "RuntimeError"
            assert data["errors"][0]["client_ip"] == "127.0.0.1"
        finally:
            _cleanup_overrides()


# ── /admin/stats pg_database_size failure (#116) ─────────────────────────


class TestAdminStatsPgSizeFailure:
    def test_stats_when_pg_database_size_unavailable(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(id=uid, email="a@b.io", name="A", provider="github", provider_user_id="a")
        admin.is_admin = True

        class Db(FakeAdminDb):
            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                low = compiled.lower()
                if "count(" in low and "sessions" in low:
                    return FakeResult(0)
                if "count(" in low and "wandb_credentials" in low:
                    return FakeResult(0)
                if "platform_settings" in compiled and "WHERE" in compiled.upper():
                    for key, val in self.settings.items():
                        if f"'{key}'" in compiled:
                            return FakeResult(PlatformSetting(key=key, value=str(val)))
                    return FakeResult(None)
                if "pg_database_size" in low:
                    raise Exception("pg_database_size not available in test")
                return FakeResult(None)

        db = Db(users={uid: admin})
        db.settings = {"login_enabled": "true"}
        client = _seed_admin_client(monkeypatch, db, admin)
        try:
            resp = client.get("/admin/stats")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["db_size_bytes"] == "unavailable"
            assert data["sessions_running"] == 0
        finally:
            _cleanup_overrides()


# ── _enforce_login_enabled on OAuth endpoints (#116) ────────────────────


class TestLoginDisabled:
    def test_github_login_rejected_when_disabled(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(id=uid, email="a@b.io", name="A", provider="github", provider_user_id="a")
        admin.is_admin = True

        db = FakeAdminDb(users={uid: admin}, settings={})

        async def _db_factory():
            yield db

        app.dependency_overrides[arena.main.get_db] = _db_factory
        client = TestClient(app)
        try:
            resp = client.get("/auth/github/login", follow_redirects=False)
            assert resp.status_code == 403, resp.text
            assert "disabled" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides()

    def test_google_login_rejected_when_disabled(self, monkeypatch):
        uid = uuid.uuid4()
        admin = User(id=uid, email="a@b.io", name="A", provider="github", provider_user_id="a")
        admin.is_admin = True

        db = FakeAdminDb(users={uid: admin}, settings={})

        async def _db_factory():
            yield db

        app.dependency_overrides[arena.main.get_db] = _db_factory
        client = TestClient(app)
        try:
            resp = client.get("/auth/google/login", follow_redirects=False)
            assert resp.status_code == 403, resp.text
            assert "disabled" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides()