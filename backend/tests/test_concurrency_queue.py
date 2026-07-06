"""Tests for the game-concurrency queue (#117): admission gate, 202
queueing, queued-action rejection, and the drainer promotion loop.
"""
import datetime
import os
import uuid

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-cq" * 4)

import importlib  # noqa: E402
import pytest  # noqa: E402

import arena.main  # noqa: E402
importlib.reload(arena.main)

from arena.concurrency import (  # noqa: E402
    evaluate_admission,
    promote_queued_sessions,
)
from arena.settings import get_settings  # noqa: E402
from arena.models.platform_setting import PlatformSetting  # noqa: E402


# ── Fake DB ─────────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, value=None, scalars_seq=None):
        self._value = value
        self._scalars_seq = scalars_seq or []

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return _Scalars(self._scalars_seq)


class _Scalars:
    def __init__(self, rows):
        self._rows = list(rows)
        self._iter = iter(self._rows)

    def __iter__(self):
        return iter(self._rows)

    def all(self):
        return list(self._rows)


class _FakeRow:
    """Minimal SessionModel-like for count + drainer promotion."""

    def __init__(self, sid=None, user_id=None, status="ready", created_at=None):
        self.id = sid or str(uuid.uuid4())
        self.user_id = user_id
        self.status = status
        self.created_at = created_at or datetime.datetime.now(datetime.timezone.utc)
        self.state_json = {}
        self.config_json = {"game": "colonelblotto"}
        self.config_hash = ""
        self.player_tokens_json = {}
        self.agents_json = {}
        self.messages_json = []
        self.wandb_config_json = None
        self.wandb_run_json = None
        self.error_message = None
        self.locked = False


class FakeDb:
    """Stores _FakeRow + PlatformSetting rows; dispatches count/select."""

    def __init__(self, rows=None, settings_rows=None):
        self.rows = rows if rows is not None else []
        self.settings_rows = settings_rows if settings_rows is not None else {}
        self.added = []

    async def execute(self, stmt):
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)

        # platform_settings lookup → return the stored row or None
        if "platform_settings" in compiled and "WHERE" in compiled.upper():
            for key, val in self.settings_rows.items():
                if f"'{key}'" in compiled:
                    return _FakeResult(PlatformSetting(key=key, value=val))
            return _FakeResult(None)

        # select(func.count()) ... WHERE sessions.status IN (...) / = 'queued'
        if "count(" in compiled.lower() and "sessions" in compiled:
            statuses = []
            for s in ("ready", "running", "queued", "completed", "failed"):
                if f"'{s}'" in compiled:
                    statuses.append(s)
            user_filter = None
            for r in self.rows:
                if r.user_id is not None and f"'{str(r.user_id)}'" in compiled:
                    user_filter = r.user_id
                    break
            count = 0
            for r in self.rows:
                if r.status in statuses:
                    if user_filter is not None and r.user_id != user_filter:
                        continue
                    count += 1
            return _FakeResult(count)

        # select(SessionModel) ... WHERE status='queued' ORDER BY created_at LIMIT n
        if "FROM sessions" in compiled and "queued" in compiled:
            queued = [r for r in self.rows if r.status == "queued"]
            queued.sort(key=lambda r: r.created_at)
            import re as _re
            m = _re.search(r"LIMIT (\d+)", compiled)
            if m:
                queued = queued[: int(m.group(1))]
            return _FakeResult(scalars_seq=queued)

        # select(SessionModel).where(id == ...) used by get_session_status
        if "FROM sessions" in compiled:
            for r in self.rows:
                if f"'{r.id}'" in compiled:
                    return _FakeResult(r)
            return _FakeResult(None)

        return _FakeResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        for obj in self.added:
            if isinstance(obj, _FakeRow):
                self.rows.append(obj)
            self.added = []


class FakeBroker:
    def __init__(self):
        self.published = []

    async def publish(self, channel, message):
        self.published.append((channel, message))


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── evaluate_admission ───────────────────────────────────────────────────


class TestEvaluateAdmission:
    @pytest.mark.asyncio
    async def test_admits_when_under_both_limits(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "5")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS_PER_USER", "2")
        get_settings.cache_clear()
        db = FakeDb(rows=[])
        result = await evaluate_admission(db, "u1")
        assert result.queued is False
        assert result.active_global == 0

    @pytest.mark.asyncio
    async def test_queues_when_global_limit_reached(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "2")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS_PER_USER", "10")
        get_settings.cache_clear()
        rows = [_FakeRow(status="ready"), _FakeRow(status="running")]
        db = FakeDb(rows=rows)
        result = await evaluate_admission(db, "u1")
        assert result.queued is True
        assert result.position == 1  # no queued rows yet
        assert result.max_concurrent_sessions == 2

    @pytest.mark.asyncio
    async def test_queues_when_per_user_limit_reached(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "100")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS_PER_USER", "1")
        get_settings.cache_clear()
        uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        rows = [_FakeRow(user_id=uid, status="ready")]
        db = FakeDb(rows=rows)
        result = await evaluate_admission(db, str(uid))
        assert result.queued is True
        assert result.position == 1

    @pytest.mark.asyncio
    async def test_queue_position_counts_existing_queued(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "1")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS_PER_USER", "100")
        get_settings.cache_clear()
        rows = [
            _FakeRow(status="ready"),
            _FakeRow(status="queued"),
            _FakeRow(status="queued"),
        ]
        db = FakeDb(rows=rows)
        result = await evaluate_admission(db, "u1")
        assert result.queued is True
        assert result.position == 3  # 2 queued ahead + self

    @pytest.mark.asyncio
    async def test_db_setting_overrides_env(self, monkeypatch):
        """A platform_settings row takes priority over the env var."""
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "50")
        get_settings.cache_clear()
        rows = [_FakeRow(status="ready")]
        db = FakeDb(rows=rows, settings_rows={"max_concurrent_sessions": "1"})
        result = await evaluate_admission(db, "u1")
        assert result.queued is True
        assert result.max_concurrent_sessions == 1


# ── drainer ──────────────────────────────────────────────────────────────


class TestDrainer:
    @pytest.mark.asyncio
    async def test_promotes_oldest_queued_when_slot_free(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "2")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS_PER_USER", "10")
        get_settings.cache_clear()
        oldest = _FakeRow(sid="oldest", status="queued", created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc))
        newer = _FakeRow(sid="newer", status="queued", created_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc))
        active = _FakeRow(sid="active", status="ready")
        db = FakeDb(rows=[active, oldest, newer])
        broker = FakeBroker()
        promoted = await promote_queued_sessions(db, broker)
        assert promoted == 1
        assert oldest.status == "ready"
        assert newer.status == "queued"
        assert any(
            msg.get("event") == "session_promoted" and msg.get("session_id") == "oldest"
            for _, msg in broker.published
        )

    @pytest.mark.asyncio
    async def test_per_user_cap_blocks_promotion(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "10")
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS_PER_USER", "1")
        get_settings.cache_clear()
        u2 = "11111111-1111-1111-1111-111111111112"
        queued = _FakeRow(user_id=uuid.UUID(u2), status="queued")
        active_u2 = _FakeRow(user_id=uuid.UUID(u2), status="ready")
        db = FakeDb(rows=[active_u2, queued])
        broker = FakeBroker()
        await promote_queued_sessions(db, broker)
        assert queued.status == "queued"

    @pytest.mark.asyncio
    async def test_drainer_idempotent_when_nothing_queued(self, monkeypatch):
        monkeypatch.setenv("MAX_CONCURRENT_SESSIONS", "2")
        get_settings.cache_clear()
        db = FakeDb(rows=[_FakeRow(status="ready"), _FakeRow(status="completed")])
        broker = FakeBroker()
        promoted = await promote_queued_sessions(db, broker)
        assert promoted == 0
        assert broker.published == []


# ── endpoint: create_experiment returns 202 when queued ───────────────────


class TestCreateExperimentQueuesAtCapacity:
    def test_returns_202_with_queue_position(self, monkeypatch):
        """When evaluate_admission says 'queued', POST /experiment returns 202."""
        import arena.main as _m
        from arena.concurrency import AdmissionDecision as _AD

        async def _fake_admit(db, user_id):
            return _AD(
                queued=True,
                position=2,
                max_concurrent_sessions=1,
                max_concurrent_sessions_per_user=1,
                active_global=1,
                active_user=1,
            )

        monkeypatch.setattr("arena.main.evaluate_admission", _fake_admit)

        # Reuse the existing full-flow fake DB shape from test_config_echo.
        from fastapi.testclient import TestClient
        from arena.db import get_db
        from arena.auth.dependencies import require_user, LOCAL_USER_ID

        class _Broker:
            async def publish(self, channel, message):
                pass

        class _Result:
            def __init__(self, value=None, scalars_seq=None):
                self._v = value
                self._seq = scalars_seq or []

            def scalar_one_or_none(self):
                return self._v

            def scalar_one(self):
                return self._v

            def scalars(self):
                return self

            def all(self):
                return list(self._seq)

        class _QueuedRow:
            def __init__(self, sid):
                self.id = sid
                self.status = "queued"
                self.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
                self.user_id = str(LOCAL_USER_ID)

        class _Db:
            def __init__(self):
                self._store = {}

            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                if "users" in compiled and "local" in compiled:
                    from arena.models.user import User
                    u = User(id=LOCAL_USER_ID)
                    u.id = LOCAL_USER_ID
                    return _Result(u)
                if "FROM sessions" in compiled and "queued" in compiled:
                    return _Result(scalars_seq=[])
                if "count(" in compiled.lower() and "sessions" in compiled:
                    return _Result(0)
                if "platform_settings" in compiled:
                    return _Result(None)
                for sid, row in self._store.items():
                    if str(sid) in compiled:
                        return _Result(row)
                return _Result(None)

            def add(self, obj):
                self._store[str(obj.id)] = obj

            async def commit(self):
                pass

            async def refresh(self, obj):
                pass

            async def rollback(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        db = _Db()

        async def _db_factory():
            yield db

        async def _user():
            # require_user in local mode calls _ensure_local_user → refresh.
            from arena.models.user import User
            return User(id=LOCAL_USER_ID)

        _m.app.dependency_overrides[get_db] = _db_factory
        _m.app.dependency_overrides[require_user] = _user
        _m.app.dependency_overrides[_m.get_broker] = lambda: _Broker()
        try:
            client = TestClient(_m.app)
            payload = {
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
            }
            resp = client.post("/experiment", json=payload)
            assert resp.status_code == 202, resp.text
            data = resp.json()
            assert data["status"] == "queued"
            assert data["queue_position"] == 2
            assert data.get("player_tokens")  # tokens minted for later use
        finally:
            _m.app.dependency_overrides.clear()