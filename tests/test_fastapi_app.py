import os
os.environ["API_PREFIX"] = ""

import pytest
from fastapi.testclient import TestClient

from nash_arena.main import SESSIONS, app, bearer_token, config_from_request


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
            if sid in compiled:
                return FakeResult(row)
        return FakeResult(None)

    async def merge(self, obj):
        self._store[obj.id] = obj

    async def commit(self):
        pass


def valid_payload(rounds=1):
    return {
        "game": "blotto",
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


def setup_function():
    SESSIONS.clear()


def test_config_from_request_builds_experiment_config():
    config = config_from_request(valid_payload(rounds=3))

    assert config.game == "blotto"
    assert config.rounds == 3
    assert config.budget == [10, 10]
    assert [field.id for field in config.battlefields] == ["A", "B", "C"]


def test_bearer_token_extracts_token():
    assert bearer_token("Bearer tok_123") == "tok_123"


def test_create_experiment_returns_session_and_tokens():
    client = TestClient(app)

    response = client.post("/api/frontend/experiment", json=valid_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] in SESSIONS
    assert data["config_hash"].startswith("sha256:")
    assert set(data["player_tokens"]) == {"A", "B"}
    assert data["player_tokens"]["A"] != data["player_tokens"]["B"]


def test_create_experiment_stores_wandb_runtime_config_without_leaking_key():
    client = TestClient(app)
    payload = {
        **valid_payload(),
        "wandb": {
            "api_key": "wandb-secret",
            "project": "arena-runs",
            "entity": "lab",
            "run_name": "run-1",
            "tags": ["blotto"],
        },
    }

    response = client.post("/api/frontend/experiment", json=payload)

    assert response.status_code == 200
    body = response.json()
    session = SESSIONS[body["session_id"]]
    assert session.runtime_config.wandb is not None
    assert session.runtime_config.wandb.api_key == "wandb-secret"
    assert session.runtime_config.to_safe_dict()["wandb"]["api_key"] == "[redacted]"
    assert "wandb-secret" not in str(body)


def test_prefixed_game_routes_require_internal_token(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_INTERNAL_API_TOKEN", "secret")
    client = TestClient(app)

    response = client.post("/api/game/experiment", json=valid_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal API token"


def test_unprefixed_game_routes_are_not_mounted(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_INTERNAL_API_TOKEN", "secret")
    client = TestClient(app)

    response = client.post("/experiment", json=valid_payload())

    assert response.status_code == 405


def test_openapi_only_exposes_segmented_game_surfaces():
    client = TestClient(app)

    paths = set(client.get("/openapi.json").json()["paths"])

    assert "/experiment" not in paths
    assert "/session/{session_id}/state" not in paths
    assert "/session/{session_id}/action" not in paths
    assert "/session/{session_id}/results" not in paths
    assert "/api/game/experiment" in paths
    assert "/api/frontend/experiment" in paths
    assert "/api/stats/experiments" in paths


def test_prefixed_game_routes_create_and_play_session_with_internal_token(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_INTERNAL_API_TOKEN", "secret")
    client = TestClient(app)
    internal_headers = {"X-Nash-Arena-Internal-Token": "secret"}

    created = client.post(
        "/api/game/experiment",
        headers=internal_headers,
        json=valid_payload(rounds=1),
    )

    assert created.status_code == 200
    data = created.json()
    session_id = data["session_id"]
    token_a = data["player_tokens"]["A"]
    token_b = data["player_tokens"]["B"]

    state = client.get(
        f"/api/game/session/{session_id}/state",
        headers=internal_headers,
    )
    assert state.status_code == 200
    assert state.json()["awaiting"] == ["A", "B"]

    first = client.post(
        f"/api/game/session/{session_id}/action",
        headers={
            **internal_headers,
            "Authorization": f"Bearer {token_a}",
        },
        json={"allocation": [10, 0, 0]},
    )
    second = client.post(
        f"/api/game/session/{session_id}/action",
        headers={
            **internal_headers,
            "Authorization": f"Bearer {token_b}",
        },
        json={"allocation": [0, 5, 5]},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    results = client.get(
        f"/api/game/session/{session_id}/results",
        headers=internal_headers,
    )
    assert results.status_code == 200
    assert results.json()["winner"] == "B"


def test_frontend_routes_create_and_play_session():
    client = TestClient(app)

    created = client.post("/api/frontend/experiment", json=valid_payload(rounds=1))

    assert created.status_code == 200
    data = created.json()
    session_id = data["session_id"]
    token_a = data["player_tokens"]["A"]
    token_b = data["player_tokens"]["B"]

    state = client.get(f"/api/frontend/session/{session_id}/state")
    assert state.status_code == 200
    assert state.json()["awaiting"] == ["A", "B"]

    first = client.post(
        f"/api/frontend/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [10, 0, 0]},
    )
    second = client.post(
        f"/api/frontend/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"allocation": [0, 5, 5]},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    results = client.get(f"/api/frontend/session/{session_id}/results")
    assert results.status_code == 200
    assert results.json()["winner"] == "B"


def test_create_experiment_rejects_invalid_config():
    client = TestClient(app)
    payload = valid_payload()
    payload["players"] = 3

    response = client.post("/api/frontend/experiment", json=payload)

    assert response.status_code == 400
    assert "2 players" in response.json()["detail"]


def test_get_state_returns_public_state_without_tokens():
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload(rounds=2)).json()

    response = client.get(f"/api/frontend/session/{created['session_id']}/state")

    assert response.status_code == 200
    state = response.json()
    assert state["session_id"] == created["session_id"]
    assert state["round"] == 1
    assert state["round_total"] == 2
    assert state["awaiting"] == ["A", "B"]
    assert "player_tokens" not in state


def test_submit_action_requires_bearer_token():
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload()).json()

    response = client.post(
        f"/api/frontend/session/{created['session_id']}/action",
        json={"allocation": [10, 0, 0]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "missing bearer token"


def test_submit_action_rejects_invalid_token():
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload()).json()

    response = client.post(
        f"/api/frontend/session/{created['session_id']}/action",
        headers={"Authorization": "Bearer bad-token"},
        json={"allocation": [10, 0, 0]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid player token"


def test_submit_actions_advance_session_and_results_include_metrics():
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload(rounds=1)).json()
    session_id = created["session_id"]
    token_a = created["player_tokens"]["A"]
    token_b = created["player_tokens"]["B"]

    first = client.post(
        f"/api/frontend/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [10, 0, 0]},
    )
    second = client.post(
        f"/api/frontend/session/{session_id}/action",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"allocation": [0, 5, 5]},
    )

    assert first.status_code == 200
    assert first.json()["awaiting"] == ["B"]
    assert second.status_code == 200
    assert second.json()["phase"] == "complete"

    results = client.get(f"/api/frontend/session/{session_id}/results")
    assert results.status_code == 200
    body = results.json()
    assert body["winner"] == "B"
    assert body["total_scores"] == {"A": 1, "B": 2}
    assert "metrics" in body


def test_duplicate_action_returns_conflict():
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload(rounds=2)).json()
    token_a = created["player_tokens"]["A"]

    client.post(
        f"/api/frontend/session/{created['session_id']}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [10, 0, 0]},
    )
    response = client.post(
        f"/api/frontend/session/{created['session_id']}/action",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"allocation": [0, 10, 0]},
    )

    assert response.status_code == 409
    assert "already submitted" in response.json()["detail"]


def test_results_before_completion_returns_conflict():
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload(rounds=2)).json()

    response = client.get(f"/api/frontend/session/{created['session_id']}/results")

    assert response.status_code == 409
    assert "complete" in response.json()["detail"]


def test_unknown_session_returns_not_found():
    client = TestClient(app)

    response = client.get("/api/frontend/session/missing/state")

    assert response.status_code == 404
    assert response.json()["detail"] == "session not found"


def test_fastapi_serves_visualizer_index():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Blotto Experiment Visualizer" in response.text
    assert "/app.js" in response.text


def test_fastapi_serves_visualizer_javascript():
    client = TestClient(app)

    response = client.get("/app.js")

    assert response.status_code == 200
    assert "POST" in response.text
    assert "/api/frontend/experiment" in response.text
    assert "/api/run-experiment" not in response.text
    assert "/api/huggingface-models" not in response.text
    assert "llm-model" not in response.text


def test_list_games_returns_registered_blotto_game():
    client = TestClient(app)

    response = client.get("/games")

    assert response.status_code == 200
    games = response.json()
    assert games[0]["name"] == "blotto"
    assert games[0]["players"] == {"min": 2, "max": 2}


def test_prefixed_catalog_routes_return_registered_blotto_game():
    client = TestClient(app)

    response = client.get("/api/catalog/games")

    assert response.status_code == 200
    games = response.json()
    assert games[0]["name"] == "blotto"
    assert games[0]["players"] == {"min": 2, "max": 2}


def test_frontend_games_route_lists_registered_blotto_game():
    client = TestClient(app)

    response = client.get("/api/frontend/games")

    assert response.status_code == 200
    games = response.json()
    assert games[0]["name"] == "blotto"
    assert games[0]["players"] == {"min": 2, "max": 2}


def test_stats_routes_require_user_api_token(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_USER_API_TOKEN", "user-secret")
    client = TestClient(app)

    response = client.get("/api/stats/experiments")

    assert response.status_code == 401
    assert response.json()["detail"] == "missing bearer token"


def test_stats_routes_reject_invalid_user_api_token(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_USER_API_TOKEN", "user-secret")
    client = TestClient(app)

    response = client.get(
        "/api/stats/experiments",
        headers={"Authorization": "Bearer wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid user API token"


def test_stats_routes_list_experiments(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_USER_API_TOKEN", "user-secret")
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload(rounds=2)).json()

    response = client.get(
        "/api/stats/experiments",
        headers={"Authorization": "Bearer user-secret"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "session_id": created["session_id"],
            "config_hash": created["config_hash"],
            "phase": "awaiting_action",
            "round": 1,
            "round_total": 2,
        }
    ]


def test_stats_routes_get_experiment_detail(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_USER_API_TOKEN", "user-secret")
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload()).json()

    response = client.get(
        f"/api/stats/experiments/{created['session_id']}",
        headers={"Authorization": "Bearer user-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == created["session_id"]
    assert body["config_hash"] == created["config_hash"]
    assert body["state"]["phase"] == "awaiting_action"
    assert "results" not in body


def test_stats_routes_metrics_before_completion_returns_conflict(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_USER_API_TOKEN", "user-secret")
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload()).json()

    response = client.get(
        f"/api/stats/experiments/{created['session_id']}/metrics",
        headers={"Authorization": "Bearer user-secret"},
    )

    assert response.status_code == 409
    assert "complete" in response.json()["detail"]


def test_stats_routes_metrics_after_completion(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_USER_API_TOKEN", "user-secret")
    client = TestClient(app)
    created = client.post("/api/frontend/experiment", json=valid_payload(rounds=1)).json()
    session_id = created["session_id"]

    client.post(
        f"/api/frontend/session/{session_id}/action",
        headers={"Authorization": f"Bearer {created['player_tokens']['A']}"},
        json={"allocation": [10, 0, 0]},
    )
    client.post(
        f"/api/frontend/session/{session_id}/action",
        headers={"Authorization": f"Bearer {created['player_tokens']['B']}"},
        json={"allocation": [0, 5, 5]},
    )

    response = client.get(
        f"/api/stats/experiments/{session_id}/metrics",
        headers={"Authorization": "Bearer user-secret"},
    )

    assert response.status_code == 200
    assert response.json()["total_payoff"] == {"A": 1, "B": 2}


def test_get_game_directory_details_metrics_and_prompts():
    client = TestClient(app)

    details = client.get("/games/blotto")
    metrics = client.get("/games/blotto/metrics")
    prompts = client.get("/games/blotto/prompts")

    assert details.status_code == 200
    assert details.json()["name"] == "blotto"
    assert metrics.status_code == 200
    assert metrics.json()["metrics"][0]["name"] == "total_payoff"
    assert prompts.status_code == 200
    assert prompts.json()["action_format"]["type"] == "json_array"


def test_get_game_skill_routes():
    client = TestClient(app)

    direct = client.get("/games/blotto/skill")
    prefixed = client.get("/api/catalog/games/blotto/skill")

    assert direct.status_code == 200
    assert prefixed.status_code == 200
    assert direct.json()["game"] == "blotto"
    assert "submit_action" in direct.json()["skill"]
    assert "Use MCP tools only." in direct.json()["skill"]
    assert prefixed.json() == direct.json()


def test_get_unknown_game_returns_not_found():
    client = TestClient(app)

    response = client.get("/games/missing")

    assert response.status_code == 404
    assert "game not found" in response.json()["detail"]
