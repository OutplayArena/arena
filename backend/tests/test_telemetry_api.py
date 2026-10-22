"""HTTP contract and access checks with SQLAlchemy-aware in-memory query fakes."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from arena.auth.dependencies import require_user
from arena.db import get_db
from arena.models.session import SessionModel
from arena.telemetry import api
from fastapi import FastAPI
from fastapi.testclient import TestClient

OWNER = uuid4()
OTHER = uuid4()


class Result:
    def __init__(self, value=None, rows=()):
        self.value = value
        self.rows = list(rows)

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.rows


class Db:
    def __init__(self, rows, events):
        self.rows = rows
        self.events = events
        self.event_query_limits = []

    async def execute(self, statement):
        compiled = statement.compile()
        params = compiled.params
        entity = statement.column_descriptions[0].get("entity")
        if entity is SessionModel:
            return Result(self.rows.get(params["id_1"]))
        matches = [
            event for event in self.events if event.session_id == params["session_id_1"]
        ]
        if "max(" in str(compiled):
            return Result(max((event.id for event in matches), default=None))
        if "id_1" in params:
            matches = [event for event in matches if event.id > params["id_1"]]
        if "id_2" in params:
            matches = [event for event in matches if event.id <= params["id_2"]]
        if "event_type_1" in params:
            matches = [
                event for event in matches if event.event_type == params["event_type_1"]
            ]
        limit = params["param_1"]
        self.event_query_limits.append(limit)
        return Result(rows=sorted(matches, key=lambda event: event.id)[:limit])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def session(session_id="session-1", **changes):
    values = {
        "id": session_id,
        "user_id": OWNER,
        "status": "completed",
        "is_public": False,
        "config_json": {"game": "rock_paper_scissors", "players": 2, "seed": 1},
        "config_hash": "sha256:research",
        "agents_json": {"A": "researcher-agent"},
        "state_json": {"history": [], "total_scores": {"A": 1, "B": 0}},
        "player_tokens_json": {
            "A": "NEVER_EXPORT_THIS",
            "B": "NEVER_EXPORT_THIS_EITHER",
        },
    }
    values.update(changes)
    return SimpleNamespace(**values)


def event(
    event_id, event_type="action.accepted", *, session_id="session-1", payload=None
):
    return SimpleNamespace(
        id=event_id,
        schema_version=1,
        session_id=session_id,
        event_type=event_type,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        player_id="A",
        round_number=1,
        agent_id="researcher-agent",
        payload_json={"action": "rock", "server_apply_ms": 1, **(payload or {})},
    )


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    db = Db(
        {"session-1": session(), "session-2": session("session-2")},
        [
            event(
                1,
                "session.created",
                payload={"arena_version": "0.4.0", "players": ["A", "B"]},
            ),
            event(2),
            event(3, session_id="session-2"),
            event(5),
            event(
                8,
                "session.completed",
                payload={
                    "total_scores": {"A": 1, "B": 0},
                    "winner": "A",
                    "rounds_completed": 1,
                },
            ),
        ],
    )
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_user] = lambda: SimpleNamespace(id=OWNER)
    monkeypatch.setattr(api, "async_session", lambda: db)
    with TestClient(app) as http:
        yield http, db, app


def test_owner_report_has_versioned_private_research_data(client):
    http, _, _ = client
    response = http.get("/api/session/session-1/telemetry")
    assert response.status_code == 200
    report = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert report["schema_version"] == 1
    assert report["session_id"] == "session-1"
    assert report["summary"]["action_count"] == 2
    assert report["coverage"]["complete"] is True
    assert "NEVER_EXPORT_THIS" not in response.text


@pytest.mark.parametrize(
    "path", ["", "/events", "/export?format=json", "/export?format=jsonl"]
)
def test_other_users_cannot_read_traces_even_when_session_is_public(client, path):
    http, db, app = client
    db.rows["session-1"].is_public = True
    app.dependency_overrides[require_user] = lambda: SimpleNamespace(id=OTHER)
    assert http.get("/api/session/session-1/telemetry" + path).status_code == 404


def test_missing_or_unowned_legacy_session_is_not_disclosed(client):
    http, db, _ = client
    assert http.get("/api/session/missing/telemetry").status_code == 404
    db.rows["session-1"].user_id = None
    assert http.get("/api/session/session-1/telemetry").status_code == 404


@pytest.mark.parametrize("path", ["", "/events", "/export?format=jsonl"])
def test_active_sessions_do_not_disclose_hidden_actions(client, path):
    http, db, _ = client
    db.rows["session-1"].status = "running"
    response = http.get("/api/session/session-1/telemetry" + path)
    assert response.status_code == 409
    assert "after the session" in response.json()["detail"]


def test_hosted_mode_requires_authentication(client, monkeypatch):
    from arena.auth import dependencies

    http, _, app = client
    app.dependency_overrides.pop(require_user)
    monkeypatch.setattr(dependencies, "_providers_configured", lambda: True)
    assert http.get("/api/session/session-1/telemetry").status_code == 401


def test_cursor_pagination_uses_ordered_ids_and_never_crosses_sessions(client):
    http, _, _ = client
    first = http.get("/api/session/session-1/telemetry/events?limit=2").json()
    assert [event["id"] for event in first["events"]] == [1, 2]
    assert first["next_after_id"] == 2
    second = http.get(
        "/api/session/session-1/telemetry/events?limit=2&after_id=2"
    ).json()
    assert [event["id"] for event in second["events"]] == [5, 8]
    assert second["next_after_id"] is None


def test_filter_applies_before_cursor_page_limit(client):
    http, _, _ = client
    result = http.get(
        "/api/session/session-1/telemetry/events?event_type=action.accepted&limit=1"
    ).json()
    assert [event["id"] for event in result["events"]] == [2]
    assert result["next_after_id"] == 2
    result = http.get(
        "/api/session/session-1/telemetry/events?event_type=action.accepted&limit=1&after_id=2"
    ).json()
    assert [event["id"] for event in result["events"]] == [5]
    assert result["next_after_id"] is None


@pytest.mark.parametrize(
    "query", ["after_id=-1", "limit=0", "limit=501", "event_type=secret.dump"]
)
def test_invalid_event_queries_are_rejected(client, query):
    http, _, _ = client
    assert (
        http.get("/api/session/session-1/telemetry/events?" + query).status_code == 422
    )


def test_invalid_export_format_is_rejected(client):
    http, _, _ = client
    assert (
        http.get("/api/session/session-1/telemetry/export?format=csv").status_code
        == 422
    )


def test_json_export_is_downloadable_report(client):
    http, _, _ = client
    response = http.get("/api/session/session-1/telemetry/export?format=json")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.json()["coverage"]["event_count"] == 4
    assert response.headers["cache-control"] == "no-store"


def test_jsonl_export_manifest_then_chunked_scoped_events(client):
    import json

    http, db, _ = client
    # Force a multi-chunk trace, including an interspersed unrelated session.
    db.events = [
        event(1, "session.created", payload={"arena_version": "0.4.0"}),
        *[event(index) for index in range(2, 1004)],
        event(1005, session_id="session-2"),
        event(
            1006, "session.completed", payload={"total_scores": {"A": 1}, "winner": "A"}
        ),
    ]
    response = http.get("/api/session/session-1/telemetry/export?format=jsonl")
    assert response.status_code == 200
    records = [json.loads(line) for line in response.text.splitlines()]
    assert records[0]["record_type"] == "manifest"
    assert records[0]["through_event_id"] == 1006
    assert records[0]["coverage"]["event_count"] == 1004
    assert all(item["record_type"] == "event" for item in records[1:])
    assert [item["id"] for item in records[1:]] == [1, *range(2, 1004), 1006]
    assert set(db.event_query_limits) == {500}
    assert len(db.event_query_limits) == 6


def test_round_export_preserves_scores_actions_and_omits_hidden_or_secret_fields(
    client,
):
    http, db, _ = client
    db.events = [
        event(
            1,
            "round.completed",
            payload={
                "round": {
                    "round": 1,
                    "actions": {"A": "rock", "B": "scissors"},
                    "total_scores": {"A": 1, "B": 0},
                    "hole_cards": {"A": ["Ah"]},
                    "api_key": "SENSITIVE",
                    "system_prompt": "SENSITIVE",
                }
            },
        )
    ]
    response = http.get("/api/session/session-1/telemetry/events")
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["events"][0]["payload"]["round"]
    assert data["actions"] == {"A": "rock", "B": "scissors"}
    assert data["total_scores"] == {"A": 1, "B": 0}
    assert "hole_cards" not in data
    assert "SENSITIVE" not in response.text
