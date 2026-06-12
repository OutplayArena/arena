import os

os.environ["API_PREFIX"] = ""
os.environ["GITHUB_CLIENT_ID"] = ""
os.environ["GITHUB_CLIENT_SECRET"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""

import pytest
from fastapi.testclient import TestClient

from nash_arena.main import app, config_from_request
from nash_arena.db import get_db
from nash_arena.auth.dependencies import require_user, _ensure_local_user


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

    async def _bypass_auth():
        return await _ensure_local_user(db)
    app.dependency_overrides[require_user] = _bypass_auth

    yield db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_user, None)


def _valid_payload(rounds=2, **kw):
    payload: dict = {
        "game": "ultimatum",
        "players": 2,
        "rounds": rounds,
        "seed": 42,
    }
    payload.update(kw)
    return payload


class TestUltimatumConfig:
    def test_config_from_request_defaults(self):
        config = config_from_request(_valid_payload())
        assert config.game == "ultimatum"
        assert config.rounds == 2
        assert config.total == 100.0
        assert config.min_offer == 1.0

    def test_config_rejects_wrong_player_count(self):
        with pytest.raises(ValueError, match="2 players"):
            config_from_request(_valid_payload(players=3))

    def test_config_rejects_zero_total(self):
        with pytest.raises(ValueError, match="total"):
            config_from_request(_valid_payload(total=0.0))

    def test_config_rejects_zero_min_offer(self):
        with pytest.raises(ValueError, match="min_offer"):
            config_from_request(_valid_payload(min_offer=0.0))

    def test_config_hash_stable(self):
        cfg1 = config_from_request(_valid_payload(seed=11))
        cfg2 = config_from_request(_valid_payload(seed=11))
        assert cfg1.config_hash() == cfg2.config_hash()


class TestUltimatumExperimentCreation:
    def test_create_returns_session_and_tokens(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["config_hash"].startswith("sha256:")
        assert set(data["player_tokens"]) == {"A", "B"}
        assert data["session_id"] in fake_db._store

    def test_create_rejects_zero_total(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(total=0.0))
        assert response.status_code == 400

    def test_create_with_custom_total(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(total=200.0))
        assert response.status_code == 200


class TestUltimatumState:
    def test_initial_state_a_proposes(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["round"] == 1
        assert state["round_total"] == 2
        assert state["phase"] == "awaiting_proposal"
        assert state["awaiting"] == ["A"]

    def test_state_includes_total(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        state = client.get(f"/session/{created['session_id']}/state").json()
        assert state["total"] == 100.0


class TestUltimatumActionSubmission:
    def test_proposal_phase_transitions_to_response(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]

        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 40.0},
        )
        assert response.status_code == 200
        state = response.json()
        assert state["phase"] == "awaiting_response"
        assert state["awaiting"] == ["B"]

    def test_responder_cannot_act_during_proposal_phase(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_b = created["player_tokens"]["B"]
        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": "accept"},
        )
        assert response.status_code in (400, 409)

    def test_offer_above_total_returns_400(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 150.0},
        )
        assert response.status_code == 400

    def test_invalid_response_returns_400(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 40.0},
        )
        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": "maybe"},
        )
        assert response.status_code == 400

    def test_accept_advances_round(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 50.0},
        )
        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": "accept"},
        )
        assert response.status_code == 200
        state = response.json()
        assert state["round"] == 2 or state.get("complete") is True


class TestUltimatumResults:
    def _play_round(self, client, sid, token_a, token_b, offer, response_action):
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": offer},
        )
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": response_action},
        )

    def test_all_accepted(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        self._play_round(client, sid, token_a, token_b, 50.0, "accept")
        # Round 2: B proposes
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": 50.0},
        )
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "accept"},
        )

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        m = results.json()["metrics"]
        assert m["acceptance_rate"] == pytest.approx(1.0)

    def test_all_rejected(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        self._play_round(client, sid, token_a, token_b, 10.0, "reject")
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": 10.0},
        )
        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "reject"},
        )

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        m = results.json()["metrics"]
        assert m["acceptance_rate"] == pytest.approx(0.0)

    def test_results_before_completion_returns_409(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/results")
        assert response.status_code == 409

    def test_unknown_session_returns_404(self, fake_db):
        client = TestClient(app)
        assert client.get("/session/missing/results").status_code == 404


class TestUltimatumDirectoryEndpoints:
    def test_list_games_includes_ultimatum(self, fake_db):
        client = TestClient(app)
        slugs = [g["slug"] for g in client.get("/games").json()]
        assert "ultimatum" in slugs

    def test_game_details(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/ultimatum")
        assert response.status_code == 200
        assert response.json()["name"] == "Ultimatum Game"

    def test_metrics_declaration(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/ultimatum/metrics").status_code == 200

    def test_prompts(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/ultimatum/prompts").status_code == 200
