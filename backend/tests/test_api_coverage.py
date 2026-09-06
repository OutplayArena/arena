import os

os.environ["API_PREFIX"] = ""
os.environ["ENABLE_AGENT_REST_API"] = "true"
os.environ["GITHUB_CLIENT_ID"] = ""
os.environ["GITHUB_CLIENT_SECRET"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""

import importlib
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import arena.main
importlib.reload(arena.main)
from arena.main import (  # noqa: E402
    ActionRequest,
    HumanActionRequest,
    MailboxSendRequest,
    app,
    get_broker,
    _session_summary,
    _api_key_response,
    _provider_configured,
    game_registry_error,
    action_error,
    bearer_token,
    sanitize_for_json,
)
from arena.db import get_db  # noqa: E402
from arena.auth.dependencies import (  # noqa: E402
    require_user,
    get_local_or_optional_user,
    get_current_user,
)
from arena.models.api_key import ApiKey  # noqa: E402
from arena.models.session import SessionModel  # noqa: E402
from arena.models.user import User  # noqa: E402


class FakeBroker:
    def __init__(self, db=None):
        self._db = db
        self._cache: dict[str, Any] = {}
        self.published: list[tuple[str, dict]] = []
        self.enqueued: list[tuple[str, dict]] = []

    async def publish(self, channel, message):
        self.published.append((channel, message))

    async def cache_get(self, key):
        return self._cache.get(key)

    async def cache_set(self, key, value, ttl=None):
        self._cache[key] = value

    async def enqueue(self, queue, message):
        self.enqueued.append((queue, message))
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
            yield None


class FakeResult:
    def __init__(self, value, row_tuples: bool = False):
        self._value = value
        self._row_tuples = row_tuples

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        if self._value is None:
            raise Exception("No row found")
        return self._value

    def fetchall(self):
        if self._value is None:
            return []
        if isinstance(self._value, list):
            return [r for r in self._value if r is not None]
        return [self._value]

    def scalar(self):
        if self._row_tuples:
            return None
        return self._value

    def scalars(self):
        class _Scalars:
            def __init__(self, v):
                self._v = v

            def all(self):
                if self._v is None:
                    return []
                if isinstance(self._v, list):
                    return [r for r in self._v if r is not None]
                return [self._v]

            def fetchall(self):
                if self._v is None:
                    return []
                if isinstance(self._v, list):
                    return [r for r in self._v if r is not None]
                return [self._v]

        return _Scalars(self._value)


class _FakeRow:
    def __init__(self, *positional, **kwargs):
        self._positional = list(positional)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._positional[key]
        return getattr(self, key)

    def keys(self):
        return [k for k in self.__dict__ if not k.startswith("_") and k != "_positional"]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return None


class FakeDb:
    def __init__(self):
        self._store: dict[str, Any] = {}

    def _tables_in(self, compiled: str) -> list[str]:
        tables = []
        for cls in (SessionModel, ApiKey):
            name = cls.__tablename__
            if name in compiled:
                tables.append(name)
        return tables

    async def execute(self, stmt):
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)

        tables = self._tables_in(compiled)
        is_grouped = "GROUP BY" in compiled.upper() or "group_by" in compiled.lower()
        is_pure_count = (
            "count(" in compiled.lower()
            and "SELECT" in compiled
            and not is_grouped
        )
        is_delete = "DELETE" in compiled.upper() and "FROM" in compiled.upper()

        if is_pure_count:
            matching = self._rows_for(tables)
            return FakeResult(len(matching))

        if is_grouped and "count" in compiled.lower():
            from collections import Counter
            rows = self._rows_for(tables)
            games = Counter()
            for r in rows:
                cfg = getattr(r, "config_json", None) or {}
                game = cfg.get("game", "unknown") if isinstance(cfg, dict) else "unknown"
                games[game] += 1

            class GroupedRow:
                def __init__(self, slug, count):
                    self._slug = slug
                    self._count = count

                def __getitem__(self, key):
                    if key == 0:
                        return self._slug
                    if key == 1:
                        return self._count
                    raise IndexError(key)

                @property
                def game_count(self):
                    return self._count

            return FakeResult(
                [GroupedRow(g, c) for g, c in games.items()],
                row_tuples=True,
            )

        if is_delete:
            target_user = self._extract_user_filter(compiled)
            to_remove = [
                sid for sid, row in self._store.items()
                if self._row_matches(row, tables, target_user)
            ]
            for sid in to_remove:
                self._store.pop(sid, None)
            return FakeResult(None)

        target_user = self._extract_user_filter(compiled)
        rows = [r for r in self._rows_for(tables) if self._row_matches(r, tables, target_user)]
        if rows:
            return FakeResult(rows[0] if len(rows) == 1 else rows)
        return FakeResult(None)

    def _rows_for(self, tables: list[str]) -> list:
        out = []
        for row in self._store.values():
            tbl = getattr(row, "__tablename__", None)
            if tbl and tables and tbl in tables:
                out.append(row)
        return out

    def _extract_user_filter(self, compiled: str) -> Any:
        for table in ("api_key", "session_model"):
            for col in ("user_id",):
                marker = f"{table}.{col} = "
                idx = compiled.find(marker)
                if idx >= 0:
                    start = idx + len(marker)
                    rest = compiled[start:].strip()
                    val = rest.split("'")[1] if "'" in rest else rest.split()[0].rstrip(",")
                    return val
        return None

    def _row_matches(self, row: Any, tables: list[str], target_user: Any) -> bool:
        if target_user is None:
            return True
        row_user = getattr(row, "user_id", None)
        if row_user is None:
            return True
        return str(row_user) == str(target_user)

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

    async def delete(self, obj):
        self._store.pop(str(obj.id), None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_user() -> User:
    user = User()
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    user.avatar_url = None
    user.show_own_leaderboard_badge = False
    return user


def _valid_payload(rounds: int = 1) -> dict[str, Any]:
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


@pytest.fixture(name="client")
def client_fixture():
    db = FakeDb()
    broker = FakeBroker(db)

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_broker] = lambda: broker

    user = _make_user()

    async def _bypass_auth():
        return user

    app.dependency_overrides[require_user] = _bypass_auth
    app.dependency_overrides[get_local_or_optional_user] = _bypass_auth
    app.dependency_overrides[get_current_user] = _bypass_auth

    c = TestClient(app)
    yield c, db, broker, user
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_broker, None)
    app.dependency_overrides.pop(require_user, None)
    app.dependency_overrides.pop(get_local_or_optional_user, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(name="anon_client")
def anon_client_fixture():
    db = FakeDb()
    broker = FakeBroker(db)

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_broker] = lambda: broker

    async def _anon_user():
        return None

    app.dependency_overrides[get_local_or_optional_user] = _anon_user
    app.dependency_overrides[get_current_user] = _anon_user
    app.dependency_overrides.pop(require_user, None)

    c = TestClient(app)
    yield c, db, broker
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_broker, None)
    app.dependency_overrides.pop(get_local_or_optional_user, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── Healthcheck ─────────────────────────────────────────────────────────


class TestHealthcheck:
    def test_health_returns_ok(self, client):
        c, _, _, _ = client
        response = c.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ── Game registry root listings ────────────────────────────────────────


class TestRootListings:
    def test_list_games_includes_blotto(self, client):
        c, _, _, _ = client
        response = c.get("/games")
        assert response.status_code == 200
        slugs = {g["slug"] for g in response.json()}
        assert "colonelblotto" in slugs
        assert "prisonersdilemma" in slugs

    def test_get_game_returns_details(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Colonel Blotto"
        assert body["slug"] == "colonelblotto"

    def test_get_game_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/nonexistent")
        assert response.status_code == 404
        assert "game not found" in response.json()["detail"]

    def test_get_game_metrics_returns_metrics(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto/metrics")
        assert response.status_code == 200
        names = {m["name"] for m in response.json()["metrics"]}
        assert "total_payoff" in names

    def test_get_game_metrics_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/missing/metrics")
        assert response.status_code == 404

    def test_get_game_prompts_returns_action_format(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto/prompts")
        assert response.status_code == 200
        assert response.json()["action_format"]["type"] == "json_array"

    def test_get_game_prompts_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/missing/prompts")
        assert response.status_code == 404

    def test_get_game_scenarios_returns_list(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto/scenarios")
        assert response.status_code == 200
        assert "scenarios" in response.json()

    def test_get_game_scenarios_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/missing/scenarios")
        assert response.status_code == 404

    def test_get_game_agents_returns_list(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto/agents")
        assert response.status_code == 200
        assert "agents" in response.json()

    def test_get_game_agents_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/missing/agents")
        assert response.status_code == 404

    def test_get_game_skill_returns_structured_sections(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto/skill")
        assert response.status_code == 200
        body = response.json()
        assert "sections" in body
        assert "objective" in body["sections"]
        assert "action_format" in body["sections"]

    def test_get_game_skill_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/missing/skill")
        assert response.status_code == 404

    def test_get_game_manifest_returns_tools(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto/manifest")
        assert response.status_code == 200
        body = response.json()
        assert body["game"] == "colonelblotto"
        assert "tools" in body
        assert "openai_tools" in body

    def test_get_game_manifest_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/missing/manifest")
        assert response.status_code == 404


# ── Session endpoints (observation, mailbox, stream, summary) ────────


class TestSessionEndpoints:
    def test_get_observation_renders_prompt(self, client):
        c, db, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        session_id = created["session_id"]
        token = created["player_tokens"]["A"]
        c.post(
            f"/session/{session_id}/action",
            headers={"Authorization": f"Bearer {token}"},
            json={"allocation": [10, 0, 0]},
        )
        response = c.get(
            f"/session/{session_id}/observation",
            params={"player": "A"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "system" in body
        assert "turn" in body
        assert body["player_id"] == "A"

    def test_get_observation_unknown_session_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/session/missing/observation", params={"player": "A"})
        assert response.status_code == 404

    def test_get_state_returns_from_cache_when_set(self, client):
        c, db, broker, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        session_id = created["session_id"]
        broker._cache[f"session:{session_id}:state"] = {"cached": True}
        response = c.get(f"/session/{session_id}/state")
        assert response.status_code == 200
        assert response.json() == {"cached": True}

    def test_submit_action_forfeit_branch(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload(rounds=2)).json()
        session_id = created["session_id"]
        token = created["player_tokens"]["A"]
        response = c.post(
            f"/session/{session_id}/action",
            headers={"Authorization": f"Bearer {token}"},
            json={"forfeit": True},
        )
        assert response.status_code == 200
        assert "awaiting" in response.json()

    def test_submit_action_invalid_player_token_returns_401(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        response = c.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": "Bearer totes-invalid"},
            json={"allocation": [10, 0, 0]},
        )
        assert response.status_code == 401

    def test_send_mailbox_message(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        session_id = created["session_id"]
        token = created["player_tokens"]["A"]
        response = c.post(
            f"/session/{session_id}/mailbox/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "hello", "recipient": "all"},
        )
        assert response.status_code == 200
        assert response.json()["sender"] == "A"
        assert response.json()["content"] == "hello"

    def test_send_mailbox_empty_content_returns_400(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        token = created["player_tokens"]["A"]
        response = c.post(
            f"/session/{created['session_id']}/mailbox/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "   ", "recipient": "all"},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"]

    def test_send_mailbox_missing_token_returns_401(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        response = c.post(
            f"/session/{created['session_id']}/mailbox/send",
            json={"content": "hi", "recipient": "all"},
        )
        assert response.status_code == 401

    def test_send_mailbox_after_complete_returns_409(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload(rounds=1)).json()
        session_id = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]
        c.post(
            f"/session/{session_id}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": [10, 0, 0]},
        )
        c.post(
            f"/session/{session_id}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": [0, 5, 5]},
        )
        response = c.post(
            f"/session/{session_id}/mailbox/send",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"content": "late", "recipient": "all"},
        )
        assert response.status_code == 409
        assert "complete" in response.json()["detail"]

    def test_send_mailbox_after_session_failed_returns_409(self, client):
        """Regression test for #149: mailbox sends must be blocked once the
        session row is administratively failed, not just when the game's
        own state phase reaches 'complete'."""
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload(rounds=10)).json()
        session_id = created["session_id"]
        token_a = created["player_tokens"]["A"]
        c.post(
            f"/session/{session_id}/fail",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"reason": "test"},
        )
        response = c.post(
            f"/session/{session_id}/mailbox/send",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"content": "after fail", "recipient": "all"},
        )
        assert response.status_code == 409
        assert "failed" in response.json()["detail"]

    def test_get_mailbox_messages_unfiltered(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        session_id = created["session_id"]
        token = created["player_tokens"]["A"]
        c.post(
            f"/session/{session_id}/mailbox/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "hi all", "recipient": "all"},
        )
        response = c.get(f"/session/{session_id}/mailbox/messages")
        assert response.status_code == 200
        body = response.json()
        assert len(body["messages"]) == 1
        assert body["messages"][0]["content"] == "hi all"

    def test_get_mailbox_messages_filtered_by_player(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        session_id = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]
        c.post(
            f"/session/{session_id}/mailbox/send",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"content": "for B only", "recipient": "B"},
        )
        c.post(
            f"/session/{session_id}/mailbox/send",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"content": "broadcast", "recipient": "all"},
        )
        response = c.get(
            f"/session/{session_id}/mailbox/messages",
            params={"player": "A"},
        )
        assert response.status_code == 200
        messages = response.json()["messages"]
        assert any(m["sender"] == "B" for m in messages)
        assert any(m["sender"] == "A" for m in messages)

    def test_get_session_summary(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload(rounds=2)).json()
        response = c.get(f"/session/{created['session_id']}/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == created["session_id"]
        assert body["game_slug"] == "colonelblotto"
        assert body["rounds"] == 2
        # The full submitted config must be returned so the play page can
        # render the Config tab with the exact parameters the game was run
        # with (locked view for running/completed/failed sessions).
        assert body["config"]["rounds"] == 2
        assert body["config"]["game"] == "colonelblotto"

    def test_get_session_summary_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/session/missing/summary")
        assert response.status_code == 404

    def test_stream_session_returns_event_stream(self, client):
        c, _, _, _ = client
        with c.stream("GET", "/session/missing/stream") as response:
            assert response.status_code == 200

    def test_fail_session(self, client):
        c, _, broker, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        token = created["player_tokens"]["A"]
        response = c.post(
            f"/session/{created['session_id']}/fail",
            headers={"Authorization": f"Bearer {token}"},
            json={"error": "manual fail"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert any(
            q == "state:persist" for q, _ in broker.enqueued
        )

    def test_get_results(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload(rounds=1)).json()
        session_id = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]
        c.post(
            f"/session/{session_id}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": [10, 0, 0]},
        )
        c.post(
            f"/session/{session_id}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": [0, 5, 5]},
        )
        response = c.get(f"/session/{session_id}/results")
        assert response.status_code == 200
        body = response.json()
        assert body["winner"] == "B"
        assert "config" in body


# ── Session history & dashboard ───────────────────────────────────────


class TestSessionHistory:
    def test_list_sessions_returns_empty(self, client):
        c, _, _, _ = client
        response = c.get("/sessions")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["sessions"] == []

    def test_list_sessions_with_filters(self, client):
        c, _, _, _ = client
        c.post("/experiment", json=_valid_payload())
        response = c.get(
            "/sessions",
            params={"game": "colonelblotto", "limit": 10, "offset": 0},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert body["sessions"][0]["game_slug"] == "colonelblotto"

    def test_list_sessions_with_agent_filter(self, client):
        c, _, _, _ = client
        c.post(
            "/experiment",
            json={**_valid_payload(), "agent_a": "alice", "agent_b": "bob"},
        )
        response = c.get("/sessions", params={"agent": "alice"})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1

    def test_list_sessions_with_date_filter(self, client):
        c, _, _, _ = client
        c.post("/experiment", json=_valid_payload())
        response = c.get(
            "/sessions",
            params={"date_from": "2020-01-01", "date_to": "2099-12-31"},
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_delete_session(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        response = c.delete(f"/sessions/{created['session_id']}")
        assert response.status_code == 200
        assert response.json()["deleted"] == created["session_id"]

    def test_delete_session_missing_returns_404(self, client):
        c, _, _, _ = client
        response = c.delete("/sessions/missing")
        assert response.status_code == 404

    def test_dashboard_summary(self, client):
        c, _, _, _ = client
        c.post("/experiment", json=_valid_payload())
        response = c.get("/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert "total_games" in body
        assert "games" in body
        assert body["total_games"] >= 1
        assert "colonelblotto" in body["games"]


# ── API keys ───────────────────────────────────────────────────────────


class TestApiKeys:
    def test_list_keys_empty(self, client):
        c, _, _, _ = client
        response = c.get("/keys")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_key(self, client):
        c, db, _, user = client
        response = c.post("/keys", json={"name": "my-key"})
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "my-key"
        assert body["is_active"] is True
        assert "full_key" in body
        assert body["full_key"].startswith("nka_")

    def test_create_key_blank_name(self, client):
        c, _, _, _ = client
        response = c.post("/keys", json={"name": "   "})
        assert response.status_code == 200
        assert response.json()["name"] is None

    def test_list_keys_returns_user_keys(self, client):
        c, _, _, _ = client
        c.post("/keys", json={"name": "first"})
        c.post("/keys", json={"name": "second"})
        response = c.get("/keys")
        assert response.status_code == 200
        keys = response.json()
        assert len(keys) == 2
        assert {k["name"] for k in keys} == {"first", "second"}

    def test_delete_key(self, client):
        c, _, _, _ = client
        created = c.post("/keys", json={"name": "to-delete"}).json()
        response = c.delete(f"/keys/{created['id']}")
        assert response.status_code == 200
        assert response.json()["deleted"] == created["id"]

    def test_delete_key_missing_returns_404(self, client):
        c, _, _, _ = client
        fake_id = str(uuid4())
        response = c.delete(f"/keys/{fake_id}")
        assert response.status_code == 404

    def test_disable_key(self, client):
        c, _, _, _ = client
        created = c.post("/keys", json={"name": "to-disable"}).json()
        response = c.post(f"/keys/{created['id']}/disable")
        assert response.status_code == 200
        assert response.json()["disabled"] == created["id"]

    def test_disable_key_missing_returns_404(self, client):
        c, _, _, _ = client
        fake_id = str(uuid4())
        response = c.post(f"/keys/{fake_id}/disable")
        assert response.status_code == 404

    def test_enable_key(self, client):
        c, _, _, _ = client
        created = c.post("/keys", json={"name": "to-enable"}).json()
        c.post(f"/keys/{created['id']}/disable")
        response = c.post(f"/keys/{created['id']}/enable")
        assert response.status_code == 200
        assert response.json()["enabled"] == created["id"]

    def test_enable_key_missing_returns_404(self, client):
        c, _, _, _ = client
        fake_id = str(uuid4())
        response = c.post(f"/keys/{fake_id}/enable")
        assert response.status_code == 404


# ── Auth endpoints ─────────────────────────────────────────────────────


class TestAuthEndpoints:
    def test_auth_providers_empty(self, client):
        c, _, _, _ = client
        response = c.get("/auth/providers")
        assert response.status_code == 200
        body = response.json()
        assert body["github"] is False
        assert body["google"] is False

    def test_auth_me_returns_user(self, client):
        c, _, _, user = client
        response = c.get("/auth/me")
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == user.email
        assert body["name"] == user.name

    def test_auth_user_returns_user(self, client):
        c, _, _, user = client
        response = c.get("/auth/user")
        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_auth_user_anonymous_returns_401(self, anon_client):
        c, _, _ = anon_client
        response = c.get("/auth/user")
        assert response.status_code == 401


# ── Benchmark & leaderboard ────────────────────────────────────────────


class TestBenchmarkEndpoints:
    def test_benchmark_report_no_agents(self, client):
        from arena.metrics import set_global_registry, AgentRegistry
        set_global_registry(AgentRegistry())
        c, _, _, _ = client
        response = c.get("/benchmark/report")
        assert response.status_code == 200
        body = response.json()
        assert "agents" in body
        assert "ranking" in body
        assert "population" in body

    def test_benchmark_report_with_agent_ids_filter(self, client):
        c, _, _, _ = client
        response = c.get("/benchmark/report", params={"agent_ids": "a,b"})
        assert response.status_code == 200

    def test_benchmark_reset(self, client):
        c, _, _, _ = client
        response = c.delete("/benchmark/reset")
        assert response.status_code == 200
        assert response.json() == {"reset": True}


# ── Site config ────────────────────────────────────────────────────────


class TestSiteConfig:
    def test_site_config_returns_defaults(self, client):
        c, _, _, _ = client
        response = c.get("/site-config")
        assert response.status_code == 200
        body = response.json()
        assert "github_url" in body
        assert "footer" in body


# ── Internal helpers ──────────────────────────────────────────────────


class TestInternalHelpers:
    def test_bearer_token_strips_whitespace(self):
        assert bearer_token("Bearer  spaced-token  ") == "spaced-token"

    def test_bearer_token_empty_string_returns_401(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            bearer_token("Bearer ")
        assert exc.value.status_code == 401

    def test_bearer_token_no_header_returns_401(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            bearer_token(None)
        assert exc.value.status_code == 401

    def test_bearer_token_no_prefix_returns_401(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            bearer_token("Token abc")
        assert exc.value.status_code == 401

    def test_action_error_invalid_player_token_returns_401(self):
        exc = action_error(ValueError("invalid player token"))
        assert exc.status_code == 401

    def test_action_error_invalid_session_key_returns_401(self):
        exc = action_error(ValueError("invalid session key"))
        assert exc.status_code == 401

    def test_action_error_already_submitted_returns_409(self):
        exc = action_error(ValueError("already submitted"))
        assert exc.status_code == 409

    def test_action_error_already_complete_returns_409(self):
        exc = action_error(ValueError("already complete"))
        assert exc.status_code == 409

    def test_action_error_generic_returns_400(self):
        exc = action_error(ValueError("some other error"))
        assert exc.status_code == 400

    def test_game_registry_error_returns_404(self):
        from arena.game_registry import GameRegistryError
        exc = game_registry_error(GameRegistryError("game not found: foo"))
        assert exc.status_code == 404
        assert "game not found" in exc.detail

    def test_sanitize_for_json_nan_becomes_zero(self):
        result = sanitize_for_json(float("nan"))
        assert result == 0.0

    def test_sanitize_for_json_inf_becomes_zero(self):
        result = sanitize_for_json(float("inf"))
        assert result == 0.0

    def test_sanitize_for_json_neg_inf_becomes_zero(self):
        result = sanitize_for_json(float("-inf"))
        assert result == 0.0

    def test_sanitize_for_json_passes_through_dicts(self):
        result = sanitize_for_json({"a": 1, "b": [1, 2]})
        assert result == {"a": 1, "b": [1, 2]}

    def test_sanitize_for_json_passes_through_strings(self):
        assert sanitize_for_json("hello") == "hello"

    def test_sanitize_for_json_passes_through_none(self):
        assert sanitize_for_json(None) is None

    def test_sanitize_for_json_recursive(self):
        result = sanitize_for_json({"a": float("nan"), "b": [float("inf")]})
        assert result == {"a": 0.0, "b": [0.0]}

    def test_provider_configured_both_empty(self):
        assert _provider_configured("", "") is False

    def test_provider_configured_only_id(self):
        assert _provider_configured("client-id", "") is False

    def test_provider_configured_only_secret(self):
        assert _provider_configured("", "secret") is False

    def test_provider_configured_both_present(self):
        assert _provider_configured("client-id", "secret") is True

    def test_provider_configured_whitespace_only(self):
        assert _provider_configured("   ", "   ") is False

    def test_api_key_response_from_row(self):
        row = ApiKey()
        row.id = uuid4()
        row.user_id = uuid4()
        row.key_hash = "deadbeef"
        row.key_prefix = "nks_test"
        row.name = "row-key"
        row.is_active = True
        row.last_used_at = None
        row.created_at = None
        result = _api_key_response(row)
        assert result.name == "row-key"
        assert result.is_active is True

    def test_session_summary_no_history(self):
        row = SessionModel()
        row.id = "sess-1"
        row.state_json = {}
        row.config_json = {"game": "colonelblotto", "battlefields": [], "budget": [100]}
        row.agents_json = {"A": "alice", "B": "bob"}
        row.status = "complete"
        row.locked = True
        row.created_at = None
        result = _session_summary(row)
        assert result["id"] == "sess-1"
        assert result["game_slug"] == "colonelblotto"
        assert result["winner"] is None
        # The full config must be returned so the play page can render the
        # exact parameters the game was run with in the locked Config tab.
        assert result["config"] == {
            "game": "colonelblotto",
            "battlefields": [],
            "budget": [100],
        }

    def test_session_summary_includes_full_config(self):
        # Configs can contain arbitrary game-specific fields (e.g. payoff
        # matrix for Prisoner's Dilemma, custom battlefields for Colonel
        # Blotto).  The summary must round-trip the whole dict so the
        # frontend can re-render the config form read-only.
        row = SessionModel()
        row.id = "sess-pd"
        row.state_json = {}
        row.config_json = {
            "game": "prisonersdilemma",
            "variant": "noisy",
            "players": 2,
            "rounds": 7,
            "payoff_T": 5.0,
            "payoff_R": 3.0,
            "payoff_P": 1.0,
            "payoff_S": 0.0,
            "noise": 0.1,
            "seed": 42,
            "scenario": "climate",
            "system_prompt": "negotiate well",
        }
        row.agents_json = {}
        row.status = "completed"
        row.locked = True
        row.created_at = None
        result = _session_summary(row)
        assert result["config"]["rounds"] == 7
        assert result["config"]["scenario"] == "climate"
        assert result["config"]["system_prompt"] == "negotiate well"

    def test_session_summary_with_history_winner_a(self):
        row = SessionModel()
        row.id = "sess-1"
        row.state_json = {
            "history": [
                {"total_scores": {"A": 5, "B": 2}},
            ]
        }
        row.config_json = {
            "game": "colonelblotto",
            "battlefields": [{"id": "A"}],
            "budget": [10, 10],
        }
        row.agents_json = {"A": "alice", "B": "bob"}
        row.status = "complete"
        row.locked = True
        row.created_at = None
        result = _session_summary(row)
        assert result["winner"] == "A"
        assert result["total_score_a"] == 5
        assert result["total_score_b"] == 2

    def test_session_summary_with_history_tie(self):
        row = SessionModel()
        row.id = "sess-1"
        row.state_json = {
            "history": [
                {"total_scores": {"A": 3, "B": 3}},
            ]
        }
        row.config_json = {
            "game": "colonelblotto",
            "battlefields": [],
            "budget": [10, 10],
        }
        row.agents_json = {}
        row.status = "complete"
        row.locked = False
        row.created_at = None
        result = _session_summary(row)
        assert result["winner"] == "Tie"

    def test_session_summary_with_history_winner_b(self):
        row = SessionModel()
        row.id = "sess-1"
        row.state_json = {
            "history": [
                {"scores": {"A": 1, "B": 5}},
            ]
        }
        row.config_json = {
            "game": "colonelblotto",
            "battlefields": [],
            "budget": [10, 10],
        }
        row.agents_json = {}
        row.status = "complete"
        row.locked = True
        row.created_at = None
        result = _session_summary(row)
        assert result["winner"] == "B"


# ── Validate ActionRequest / HumanActionRequest / MailboxSendRequest ──


class TestPydanticModels:
    def test_action_request_defaults(self):
        req = ActionRequest()
        assert req.allocation is None
        assert req.forfeit is False

    def test_action_request_forfeit_true(self):
        req = ActionRequest(forfeit=True)
        assert req.forfeit is True

    def test_human_action_request_defaults(self):
        req = HumanActionRequest()
        assert req.action is None
        assert req.forfeit is False

    def test_mailbox_send_request_defaults(self):
        req = MailboxSendRequest(content="hi")
        assert req.recipient == "all"

    def test_mailbox_send_request_explicit_recipient(self):
        req = MailboxSendRequest(content="hi", recipient="B")
        assert req.recipient == "B"


# ── Interactive endpoints (non-interactive game → 400) ───────────────


class TestInteractiveEndpoints:
    def test_get_interactive_schema_blotto_returns_200(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        response = c.get(
            f"/session/{created['session_id']}/interactive/schema",
            params={"player": "A"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "schema" in body
        assert "ui_metadata" in body
        assert "state" in body

    def test_get_interactive_schema_missing_session_returns_404(self, client):
        c, _, _, _ = client
        response = c.get(
            "/session/missing/interactive/schema",
            params={"player": "A"},
        )
        assert response.status_code == 404

    def test_get_interactive_state_non_interactive_falls_back(self, client):
        c, _, _, _ = client
        created = c.post("/experiment", json=_valid_payload()).json()
        response = c.get(
            f"/session/{created['session_id']}/interactive/state",
            params={"player": "A"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "session_id" in body

    def test_get_interactive_agents_returns_list(self, client):
        c, _, _, _ = client
        response = c.get("/games/colonelblotto/interactive/agents")
        assert response.status_code == 200
        assert "agents" in response.json()

    def test_get_interactive_agents_unknown_game_returns_404(self, client):
        c, _, _, _ = client
        response = c.get("/games/missing/interactive/agents")
        assert response.status_code == 404

    def test_submit_human_action_missing_session_returns_404(self, client):
        c, _, _, _ = client
        response = c.post(
            "/session/missing/interactive/action",
            headers={"Authorization": "Bearer anything"},
            params={"player": "A"},
            json={"allocation": [10, 0, 0]},
        )
        assert response.status_code == 404


# ── require_agent_api behavior ───────────────────────────────────────


class TestRequireAgentApi:
    def test_require_agent_api_disabled_no_header_returns_403(self, monkeypatch):
        from fastapi import HTTPException
        monkeypatch.setenv("ENABLE_AGENT_REST_API", "false")
        import arena.main as am
        importlib.reload(am)
        try:
            with pytest.raises(HTTPException) as exc:
                import asyncio
                asyncio.run(am.require_agent_api_dep(request=None, authorization=None, db=None))
            assert exc.value.status_code == 403
        finally:
            monkeypatch.setenv("ENABLE_AGENT_REST_API", "true")
            importlib.reload(am)


# ── get_broker not-initialized branch ────────────────────────────────


class TestGetBrokerUninitialized:
    def test_get_broker_when_broker_is_none_raises(self, monkeypatch):
        import arena.main as am
        importlib.reload(am)
        old = am._broker
        am._broker = None
        try:
            gen = am.get_broker()
            with pytest.raises(RuntimeError, match="broker not initialized"):
                # consume first item of async generator
                import asyncio
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(gen.__anext__())
                finally:
                    loop.close()
        finally:
            am._broker = old
