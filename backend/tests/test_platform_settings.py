"""Tests for arena.settings (pydantic-settings) and the platform_settings
DB helpers (get_platform_setting / set_platform_setting).
"""
import os
import uuid

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-ps" * 4)

import pytest  # noqa: E402

from arena.settings import get_settings  # noqa: E402
from arena.models.platform_setting import PlatformSetting  # noqa: E402
from arena.platform_settings import (  # noqa: E402
    get_platform_setting,
    set_platform_setting,
)


class FakeResult:
    def __init__(self, data=None):
        self._data = data

    def scalar_one_or_none(self):
        return self._data


class FakeDb:
    """Minimal async DB: stores PlatformSetting rows in a dict keyed by `key`."""

    def __init__(self):
        self.rows: dict[str, PlatformSetting] = {}
        self.added: list[PlatformSetting] = []

    async def execute(self, stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # select(PlatformSetting).where(PlatformSetting.key == <key>)
        if "platform_settings" in compiled and "WHERE" in compiled.upper():
            # Extract the key value from the literal binds.
            for k, v in self.rows.items():
                if f"'{k}'" in compiled:
                    return FakeResult(v)
            return FakeResult(None)
        return FakeResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        for obj in self.added:
            if isinstance(obj, PlatformSetting):
                self.rows[obj.key] = obj
        self.added = []


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Settings (env-var) ───────────────────────────────────────────────────


class TestSettings:
    def test_defaults_when_no_env(self, monkeypatch):
        for var in (
            "ENABLE_ADMIN_DASHBOARD",
            "ADMIN_USER_IDS",
            "MAX_CONCURRENT_SESSIONS",
            "MAX_CONCURRENT_SESSIONS_PER_USER",
            "MATCHMAKING_TTL_HOURS",
            "MATCHMAKING_SWEEPER_INTERVAL_SECONDS",
            "ENABLE_MATCHMAKING",
        ):
            monkeypatch.delenv(var, raising=False)
        get_settings.cache_clear()
        s = get_settings()
        assert s.enable_admin_dashboard is False
        assert s.max_concurrent_sessions == 50
        assert s.max_concurrent_sessions_per_user == 5
        assert s.matchmaking_ttl_hours == 24
        assert s.matchmaking_sweeper_interval_seconds == 3600
        assert s.enable_matchmaking is True
        assert s.admin_user_id_set == set()

    def test_parses_env_values(self, monkeypatch):
        monkeypatch.setenv("ENABLE_ADMIN_DASHBOARD", "true")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "7")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS_PER_USER", "2")
        monkeypatch.setenv("ADMIN_USER_IDS", "  abc-1 , DEF-2 ,")
        get_settings.cache_clear()
        s = get_settings()
        assert s.enable_admin_dashboard is True
        assert s.max_concurrent_sessions == 7
        assert s.max_concurrent_sessions_per_user == 2
        assert s.admin_user_id_set == {"abc-1", "def-2"}

    def test_admin_user_id_set_parser_handles_empty(self, monkeypatch):
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        get_settings.cache_clear()
        assert get_settings().admin_user_id_set == set()


# ── get_platform_setting (DB-first, env fallback) ────────────────────────


class TestGetPlatformSetting:
    @pytest.mark.asyncio
    async def test_returns_db_value_when_row_exists(self):
        db = FakeDb()
        db.rows["max_concurrent_sessions"] = PlatformSetting(
            key="max_concurrent_sessions", value="13"
        )
        result = await get_platform_setting(
            "max_concurrent_sessions", db, cast=int
        )
        assert result == 13

    @pytest.mark.asyncio
    async def test_falls_back_to_env_default_when_row_missing(self, monkeypatch):
        monkeypatch.delenv("MAX_CONCURRENT_SESSIONS", raising=False)
        get_settings.cache_clear()
        db = FakeDb()
        result = await get_platform_setting(
            "max_concurrent_sessions", db, cast=int
        )
        assert result == 50  # Settings default

    @pytest.mark.asyncio
    async def test_falls_back_to_env_value_when_row_missing(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "9")
        get_settings.cache_clear()
        db = FakeDb()
        result = await get_platform_setting(
            "max_concurrent_sessions", db, cast=int
        )
        assert result == 9

    @pytest.mark.asyncio
    async def test_unknown_key_returns_none(self):
        db = FakeDb()
        result = await get_platform_setting("no_such_key", db, cast=int)
        assert result is None


# ── set_platform_setting (upsert) ───────────────────────────────────────


class TestSetPlatformSetting:
    @pytest.mark.asyncio
    async def test_inserts_new_row(self):
        db = FakeDb()
        actor = uuid.uuid4()
        await set_platform_setting(
            "max_concurrent_sessions", 42, db, updated_by=actor
        )
        assert "max_concurrent_sessions" in db.rows
        assert db.rows["max_concurrent_sessions"].value == "42"
        assert db.rows["max_concurrent_sessions"].updated_by == actor

    @pytest.mark.asyncio
    async def test_updates_existing_row(self):
        db = FakeDb()
        existing = PlatformSetting(key="max_concurrent_sessions", value="50")
        db.rows["max_concurrent_sessions"] = existing
        await set_platform_setting(
            "max_concurrent_sessions", 3, db, updated_by=None
        )
        assert existing.value == "3"
        assert len(db.rows) == 1  # no duplicate

    @pytest.mark.asyncio
    async def test_bool_serialized_as_lowercased_text(self):
        db = FakeDb()
        await set_platform_setting("login_enabled", True, db)
        assert db.rows["login_enabled"].value == "true"
        await set_platform_setting("login_enabled", False, db)
        assert db.rows["login_enabled"].value == "false"