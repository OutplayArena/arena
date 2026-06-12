import os
os.environ["API_PREFIX"] = ""
os.environ["ENABLE_AGENT_REST_API"] = "true"

from pathlib import Path
import importlib
import pytest
from fastapi.testclient import TestClient

import nash_arena.main
importlib.reload(nash_arena.main)
from nash_arena.main import app, bearer_token, config_from_request  # noqa: E402
from nash_arena.db import get_db  # noqa: E402
from nash_arena.auth.dependencies import require_user, _ensure_local_user  # noqa: E402


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeDb:
    def __init__(self):
        self._store: dict[str, object] = {}

    async def execute(self, stmt):
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        for sid, row in self._store.items():
            if str(sid) in compiled:
                return FakeResult(row)
        return FakeResult(None)

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


@pytest.fixture(name="fake_db")
def fake_db_fixture():
    db = FakeDb()
    app.dependency_overrides[get_db] = lambda: db

    async def _bypass_auth():
        return await _ensure_local_user(db)
    app.dependency_overrides[require_user] = _bypass_auth

    yield db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_user, None)


def valid_payload(rounds=1):
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


def test_config_from_request_builds_experiment_config():
    config = config_from_request(valid_payload(rounds=3))

    assert config.game == "colonelblotto"
    assert config.rounds == 3
    assert config.budget == [10, 10]
    assert [field.id for field in config.battlefields] == ["A", "B", "C"]


def test_bearer_token_extracts_token():
    assert bearer_token("Bearer tok_123") == "tok_123"


def test_create_experiment_returns_session_and_tokens(fake_db):
    client = TestClient(app)

    response = client.post("/experiment", json=valid_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["config_hash"].startswith("sha256:")
    assert set(data["player_tokens"]) == {"A", "B"}
    assert data["player_tokens"]["A"] != data["player_tokens"]["B"]
    assert data["session_id"] in fake_db._store


def test_create_experiment_rejects_invalid_config(fake_db):
    client = TestClient(app)
    payload = valid_payload()
    payload["players"] = 3

    response = client.post("/experiment", json=payload)

    assert response.status_code == 400
    assert "2 players" in response.json()["detail"]


def test_get_state_returns_public_state_without_tokens(fake_db):
    client = TestClient(app)
    created = client.post("/experiment", json=valid_payload(rounds=2)).json()

    response = client.get(f"/session/{created['session_id']}/state")

    assert response.status_code == 200
    state = response.json()
    assert state["session_id"] == created["session_id"]
    assert state["round"] == 1
    assert state["round_total"] == 2
    assert state["awaiting"] == ["A", "B"]
    assert "player_tokens" not in state


def test_submit_action_requires_bearer_token(fake_db):
    client = TestClient(app)
    created = client.post("/experiment", json=valid_payload()).json()

    response = client.post(
        f"/session/{created['session_id']}/action",
        json={"allocation": [10, 0, 0]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "missing bearer token"


def test_submit_action_rejects_invalid_token(fake_db):
    client = TestClient(app)
    created = client.post("/experiment", json=valid_payload()).json()

    response = client.post(
        f"/session/{created['session_id']}/action",
        headers={"Authorization": "Bearer bad-token"},
        json={"allocation": [10, 0, 0]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid player token"


def test_submit_actions_advance_session_and_results_include_metrics(fake_db):
    client = TestClient(app)
    created = client.post("/experiment", json=valid_payload(rounds=1)).json()
    session_id = created["session_id"]
    token_a = created["player_tokens"]["A"]
    token_b = created["player_tokens"]["B"]

    first = client.post(
        f"/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [10, 0, 0]},
    )
    second = client.post(
        f"/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"allocation": [0, 5, 5]},
    )

    assert first.status_code == 200
    assert first.json()["awaiting"] == ["B"]
    assert second.status_code == 200
    assert second.json()["phase"] == "complete"

    results = client.get(f"/session/{session_id}/results")
    assert results.status_code == 200
    body = results.json()
    assert body["winner"] == "B"
    assert body["total_scores"] == {"A": 1, "B": 2}
    assert "metrics" in body


def test_duplicate_action_returns_conflict(fake_db):
    client = TestClient(app)
    created = client.post("/experiment", json=valid_payload(rounds=2)).json()
    token_a = created["player_tokens"]["A"]

    client.post(
        f"/session/{created['session_id']}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [10, 0, 0]},
    )
    response = client.post(
        f"/session/{created['session_id']}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [0, 10, 0]},
    )

    assert response.status_code == 409
    assert "already submitted" in response.json()["detail"]


def test_results_before_completion_returns_conflict(fake_db):
    client = TestClient(app)
    created = client.post("/experiment", json=valid_payload(rounds=2)).json()

    response = client.get(f"/session/{created['session_id']}/results")

    assert response.status_code == 409
    assert "complete" in response.json()["detail"]


def test_unknown_session_returns_not_found(fake_db):
    client = TestClient(app)

    response = client.get("/session/missing/state")

    assert response.status_code == 404
    assert response.json()["detail"] == "session not found"


def test_fastapi_serves_visualizer_index():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "NashArena" in response.text
    assert "/assets/index-" in response.text


def _frontend_bundle_ready() -> bool:
    import re as _re
    static = Path(__file__).resolve().parent.parent / "static"
    html = static / "index.html"
    if not html.exists():
        return False
    m = _re.search(r'src="(/assets/index-[^"]+\.js)"', html.read_text())
    return bool(m) and (static / m.group(1).lstrip("/")).exists()


@pytest.mark.skipif(not _frontend_bundle_ready(), reason="frontend bundle not built or stale")
def test_fastapi_serves_visualizer_javascript():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    import re

    match = re.search(r'src="(/assets/index-[^"]+\.js)"', response.text)
    assert match, "JS bundle script tag not found in index.html"
    js_path = match.group(1)

    js_response = client.get(js_path)
    assert js_response.status_code == 200


def test_list_games_returns_registered_blotto_game():
    client = TestClient(app)

    response = client.get("/games")

    assert response.status_code == 200
    games = response.json()
    slugs = {g["slug"]: g for g in games}
    assert "colonelblotto" in slugs
    blotto = slugs["colonelblotto"]
    assert blotto["name"] == "Colonel Blotto"
    assert blotto["players"] == {"min": 2, "max": 2}


def test_get_game_directory_details_metrics_and_prompts():
    client = TestClient(app)

    details = client.get("/games/colonelblotto")
    metrics = client.get("/games/colonelblotto/metrics")
    prompts = client.get("/games/colonelblotto/prompts")

    assert details.status_code == 200
    assert details.json()["name"] == "Colonel Blotto"
    assert metrics.status_code == 200
    assert metrics.json()["metrics"][0]["name"] == "total_payoff"
    assert prompts.status_code == 200
    assert prompts.json()["action_format"]["type"] == "json_array"


def test_get_unknown_game_returns_not_found():
    client = TestClient(app)

    response = client.get("/games/missing")

    assert response.status_code == 404
    assert "game not found" in response.json()["detail"]
