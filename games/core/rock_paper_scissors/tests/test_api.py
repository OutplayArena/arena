import os

os.environ["API_PREFIX"] = ""
for _var in ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
    os.environ.setdefault(_var, "")

import pytest
from fastapi.testclient import TestClient

from nash_arena.main import app, bearer_token, config_from_request
from nash_arena.db import get_db


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
    yield db
    app.dependency_overrides.pop(get_db, None)


def _valid_payload(rounds=3):
    return {
        "game": "rock_paper_scissors",
        "variant": "classic",
        "players": 2,
        "rounds": rounds,
        "seed": 42,
    }


class TestRPSConfig:
    def test_config_from_request_builds_rps_config(self):
        config = config_from_request(_valid_payload())
        assert config.game == "rock_paper_scissors"
        assert config.rounds == 3
        assert config.player_ids() == ["A", "B"]

    def test_config_rejects_unknown_variant(self):
        payload = _valid_payload()
        payload["variant"] = "blitz"
        with pytest.raises(ValueError, match="variant"):
            config_from_request(payload)

    def test_config_rejects_invalid_players(self):
        payload = _valid_payload()
        payload["players"] = 3
        with pytest.raises(ValueError, match="2 players"):
            config_from_request(payload)


class TestRPSExperimentCreation:
    def test_create_experiment_returns_session_and_tokens(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["config_hash"].startswith("sha256:")
        assert set(data["player_tokens"]) == {"A", "B"}
        assert data["player_tokens"]["A"] != data["player_tokens"]["B"]
        assert data["session_id"] in fake_db._store

    def test_create_experiment_rejects_invalid_variant(self, fake_db):
        client = TestClient(app)
        payload = _valid_payload()
        payload["variant"] = "blitz"
        response = client.post("/experiment", json=payload)
        assert response.status_code == 400
        assert "variant" in response.json()["detail"]


class TestRPSState:
    def test_get_state_returns_public_state(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["session_id"] == created["session_id"]
        assert state["round"] == 1
        assert state["round_total"] == 3
        assert state["phase"] == "awaiting_action"
        assert sorted(state["awaiting"]) == ["A", "B"]

    def test_get_state_unknown_session_returns_404(self, fake_db):
        client = TestClient(app)
        response = client.get("/session/missing/state")
        assert response.status_code == 404


class TestRPSActionSubmission:
    def test_submit_action_rejects_missing_token(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.post(
            f"/session/{created['session_id']}/action",
            json={"allocation": "rock"},
        )
        assert response.status_code == 401

    def test_submit_action_rejects_invalid_token(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": "Bearer bad-token"},
            json={"allocation": "rock"},
        )
        assert response.status_code == 401

    def test_submit_action_rejects_invalid_move(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "lizard"},
        )
        assert response.status_code == 400

    def test_submit_first_action_awaits_second(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "rock"},
        )
        assert response.status_code == 200
        state = response.json()
        assert state["awaiting"] == ["B"]

    def test_duplicate_action_returns_conflict(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "rock"},
        )
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "paper"},
        )
        assert response.status_code == 409

    def test_forfeit_advances_round(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": None, "forfeit": True},
        )
        assert response.status_code == 200
        state = response.json()
        assert state["history"][-1]["forfeit"] is True


class TestRPSResults:
    def test_full_game_completes_and_returns_metrics(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        moves = [("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")]
        for a_move, b_move in moves:
            client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"allocation": a_move},
            )
            resp = client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token_b}"},
                json={"allocation": b_move},
            )
        assert resp.json()["phase"] == "complete"

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        body = results.json()
        assert body["winner"] == "A"
        assert "metrics" in body
        m = body["metrics"]
        assert "total_payoff" in m
        assert "average_payoff" in m
        assert "round_win_counts" in m
        assert "round_win_rate" in m
        assert "move_frequencies" in m
        assert m["move_frequencies"]["A"]["rock"] == pytest.approx(1 / 3, abs=1e-3)
        assert m["move_frequencies"]["B"]["scissors"] == pytest.approx(1 / 3, abs=1e-3)

    def test_results_before_completion_returns_409(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/results")
        assert response.status_code == 409

    def test_tie_game_returns_winner_tie(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload(rounds=1)).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "rock"},
        )
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": "rock"},
        )
        results = client.get(f"/session/{sid}/results")
        assert results.json()["winner"] == "Tie"
        assert results.json()["metrics"]["round_win_counts"]["Tie"] == 1


class TestRPSDirectoryEndpoints:
    def test_list_games_includes_rps(self, fake_db):
        client = TestClient(app)
        response = client.get("/games")
        games = response.json()
        slugs = [g["slug"] for g in games]
        assert "rock_paper_scissors" in slugs

    def test_rps_game_details(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/rock_paper_scissors")
        assert response.status_code == 200
        assert response.json()["name"] == "Rock-Paper-Scissors"

    def test_rps_metrics_declaration(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/rock_paper_scissors/metrics")
        assert response.status_code == 200
        assert "metrics" in response.json()

    def test_rps_prompts(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/rock_paper_scissors/prompts")
        assert response.status_code == 200
        assert response.json()["action_format"]["type"] == "string"
