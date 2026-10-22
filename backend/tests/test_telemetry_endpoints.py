"""Failure, terminal-session and human-action paths of the recording endpoints."""

import os

os.environ["API_PREFIX"] = ""
os.environ["ENABLE_AGENT_REST_API"] = "true"

import pytest
from arena.auth.dependencies import _ensure_local_user, require_user
from arena.db import get_db
from arena.main import app, get_broker
from arena.models.telemetry_event import TelemetryEvent
from fastapi.testclient import TestClient


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
        return self._value

    def scalar_one(self):
        if self._value is None:
            raise LookupError("No row found")
        return self._value


class FakeDb:
    def __init__(self):
        self._store: dict[str, object] = {}
        self.events: list[TelemetryEvent] = []

    async def execute(self, stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        for sid, row in self._store.items():
            if str(sid) in compiled:
                return FakeResult(row)
        return FakeResult(None)

    def add(self, obj):
        if isinstance(obj, TelemetryEvent):
            self.events.append(obj)
            return
        self._store[str(obj.id)] = obj

    async def flush(self):
        pass

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


@pytest.fixture
def db():
    fake = FakeDb()
    app.dependency_overrides[get_db] = lambda: fake
    app.dependency_overrides[get_broker] = lambda: FakeBroker()

    async def _bypass_auth():
        return await _ensure_local_user(fake)

    app.dependency_overrides[require_user] = _bypass_auth
    yield fake
    for dependency in (get_db, get_broker, require_user):
        app.dependency_overrides.pop(dependency, None)


def create(client, rounds=1, game="rock_paper_scissors"):
    response = client.post(
        "/experiment",
        json={
            "game": game,
            "variant": "classic",
            "players": 2,
            "rounds": rounds,
            "seed": 42,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["session_id"], body["player_tokens"]


def types(db):
    return [event.event_type for event in db.events]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_unexpected_engine_error_fails_session_and_records_it(db, monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    session_id, tokens = create(client)
    from games.core.rock_paper_scissors.engine import RPSGame

    def boom(self, state, player, action):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(RPSGame, "apply_action", boom)
    response = client.post(
        f"/session/{session_id}/action",
        headers=auth(tokens["A"]),
        json={"allocation": "rock"},
    )
    assert response.status_code == 500
    assert db._store[session_id].status == "failed"
    assert "action.rejected" in types(db)
    assert "session.failed" in types(db)
    failed = next(e for e in db.events if e.event_type == "session.failed")
    assert failed.payload_json["error_type"] == "RuntimeError"


def test_fail_endpoint_is_idempotent_and_cannot_fail_completed_sessions(db):
    client = TestClient(app)
    session_id, tokens = create(client)
    first = client.post(
        f"/session/{session_id}/fail",
        headers=auth(tokens["A"]),
        json={"error": "gave up"},
    )
    assert first.status_code == 200 and first.json()["status"] == "failed"
    again = client.post(
        f"/session/{session_id}/fail",
        headers=auth(tokens["A"]),
        json={"error": "again"},
    )
    assert again.status_code == 200
    assert again.json()["error_message"] == "gave up"
    assert types(db).count("session.failed") == 1

    done_id, done_tokens = create(client)
    for player, move in (("A", "rock"), ("B", "paper")):
        client.post(
            f"/session/{done_id}/action",
            headers=auth(done_tokens[player]),
            json={"allocation": move},
        )
    assert db._store[done_id].status == "completed"
    conflict = client.post(
        f"/session/{done_id}/fail",
        headers=auth(done_tokens["A"]),
        json={"error": "late"},
    )
    assert conflict.status_code == 409
    assert db._store[done_id].status == "completed"


def human(client, session_id, token, player, **body):
    return client.post(
        f"/session/{session_id}/interactive/action",
        params={"player": player},
        headers=auth(token),
        json=body,
    )


def test_human_action_validates_before_recording(db):
    client = TestClient(app)
    session_id, tokens = create(client)
    assert human(client, session_id, tokens["A"], "B", action="rock").status_code == 403
    assert not db.events or "action.rejected" not in types(db)

    invalid = human(client, session_id, tokens["A"], "A", action="lizard")
    assert invalid.status_code == 400
    assert types(db).count("action.rejected") == 1

    ok = human(client, session_id, tokens["A"], "A", action="rock")
    assert ok.status_code == 200
    assert types(db).count("action.accepted") == 1


def test_human_forfeit_uses_the_recorded_forfeit_path(db):
    client = TestClient(app)
    session_id, tokens = create(client)
    response = human(client, session_id, tokens["A"], "A", forfeit=True)
    assert response.status_code == 200
    accepted = next(e for e in db.events if e.event_type == "action.accepted")
    assert accepted.payload_json["forfeit"] is True
    assert accepted.payload_json["action"] is None


def test_human_action_on_terminal_session_is_conflict_and_observed(db):
    client = TestClient(app)
    session_id, tokens = create(client)
    client.post(
        f"/session/{session_id}/fail", headers=auth(tokens["A"]), json={"error": "stop"}
    )
    before = types(db).count("action.rejected")
    response = human(client, session_id, tokens["A"], "A", action="rock")
    assert response.status_code == 409
    assert "failed" in response.json()["detail"]
    rejected = [e for e in db.events if e.event_type == "action.rejected"]
    assert len(rejected) == before + 1
    assert rejected[-1].payload_json["category"] == "session_failed"


def test_human_action_game_error_after_validation_fails_session(db, monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    session_id, tokens = create(client)
    from games.core.rock_paper_scissors.engine import RPSGame

    def boom(self, state, player, action):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(RPSGame, "apply_action", boom)
    response = human(client, session_id, tokens["A"], "A", action="rock")
    assert response.status_code == 500
    assert db._store[session_id].status == "failed"
    assert "session.failed" in types(db)


def test_human_value_error_after_validation_is_a_recorded_conflict(db, monkeypatch):
    client = TestClient(app)
    session_id, tokens = create(client)
    from games.core.rock_paper_scissors.engine import RPSGame

    def duplicate(self, state, player, action):
        raise ValueError("player already submitted")

    monkeypatch.setattr(RPSGame, "apply_action", duplicate)
    response = human(client, session_id, tokens["A"], "A", action="rock")
    assert response.status_code == 409
    assert "action.rejected" in types(db)


def test_human_validation_failure_is_recorded_as_a_rejection(db, monkeypatch):
    client = TestClient(app)
    session_id, tokens = create(client)
    from games.core.rock_paper_scissors.engine import RPSGame

    def reject(self, state, player, action, config):
        raise ValueError("not a legal move")

    monkeypatch.setattr(RPSGame, "validate_human_action", reject)
    response = human(client, session_id, tokens["A"], "A", action="rock")
    assert response.status_code == 400
    rejected = [e for e in db.events if e.event_type == "action.rejected"]
    assert [e.payload_json["category"] for e in rejected] == ["invalid_action"]
    assert "action.accepted" not in types(db)
