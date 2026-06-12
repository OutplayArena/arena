import os

os.environ["API_PREFIX"] = ""
os.environ["GITHUB_CLIENT_ID"] = ""
os.environ["GITHUB_CLIENT_SECRET"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["ENABLE_AGENT_REST_API"] = "true"

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


@pytest.fixture(autouse=True)
def enable_agent_rest_api():
    os.environ["ENABLE_AGENT_REST_API"] = "true"
    yield


def _valid_payload(rounds=3, **kw):
    payload: dict = {
        "game": "battle_of_the_sexes",
        "players": 2,
        "rounds": rounds,
        "seed": 42,
    }
    payload.update(kw)
    return payload


class TestBoSConfig:
    def test_config_from_request_builds_bos_config(self):
        config = config_from_request(_valid_payload())
        assert config.game == "battle_of_the_sexes"
        assert config.rounds == 3
        assert config.payoff_preferred_a == 3.0
        assert config.payoff_preferred_b == 3.0
        assert config.payoff_nonpreferred == 2.0
        assert config.payoff_mismatch == 0.0
        assert config.option_a_label == "opera"
        assert config.option_b_label == "football"

    def test_config_custom_labels(self):
        config = config_from_request(_valid_payload(option_a_label="Bach", option_b_label="Stravinsky"))
        assert config.option_a_label == "Bach"
        assert config.option_b_label == "Stravinsky"

    def test_config_rejects_wrong_player_count(self):
        payload = _valid_payload(players=3)
        with pytest.raises(ValueError, match="2 players"):
            config_from_request(payload)

    def test_config_hash_stable(self):
        cfg1 = config_from_request(_valid_payload(seed=5))
        cfg2 = config_from_request(_valid_payload(seed=5))
        assert cfg1.config_hash() == cfg2.config_hash()


class TestBoSExperimentCreation:
    def test_create_returns_session_and_tokens(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["config_hash"].startswith("sha256:")
        assert set(data["player_tokens"]) == {"A", "B"}
        assert data["session_id"] in fake_db._store

    def test_create_with_custom_labels(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(option_a_label="Bach", option_b_label="Stravinsky"))
        assert response.status_code == 200

    def test_create_rejects_wrong_player_count(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(players=4))
        assert response.status_code == 400


class TestBoSState:
    def test_state_returns_public_state(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["session_id"] == created["session_id"]
        assert state["round"] == 1
        assert state["round_total"] == 3
        assert sorted(state["awaiting"]) == ["A", "B"]

    def test_state_includes_options(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        state = client.get(f"/session/{created['session_id']}/state").json()
        assert "option_a" in state or "options" in state or "option_a_label" in state


class TestBoSActionSubmission:
    def test_submit_first_action_awaits_second(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "opera"},
        )
        assert response.status_code == 200
        assert response.json()["awaiting"] == ["B"]

    def test_submit_invalid_action_returns_400(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "chess"},
        )
        assert response.status_code == 400

    def test_duplicate_action_returns_conflict(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "opera"},
        )
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "football"},
        )
        assert response.status_code == 409


class TestBoSResults:
    def test_both_choose_opera(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        for _ in range(3):
            client.post(f"/session/{sid}/action",
                        headers={"Authorization": f"Bearer {token_a}"},
                        json={"allocation": "opera"})
            client.post(f"/session/{sid}/action",
                        headers={"Authorization": f"Bearer {token_b}"},
                        json={"allocation": "opera"})

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        body = results.json()
        assert "metrics" in body
        m = body["metrics"]
        assert m["coordination_rate"] == pytest.approx(1.0)

    def test_mismatch_outcomes(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        for _ in range(3):
            client.post(f"/session/{sid}/action",
                        headers={"Authorization": f"Bearer {token_a}"},
                        json={"allocation": "opera"})
            client.post(f"/session/{sid}/action",
                        headers={"Authorization": f"Bearer {token_b}"},
                        json={"allocation": "football"})

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        m = results.json()["metrics"]
        assert m["coordination_rate"] == pytest.approx(0.0)

    def test_results_before_completion_returns_409(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/results")
        assert response.status_code == 409

    def test_unknown_session_returns_404(self, fake_db):
        client = TestClient(app)
        assert client.get("/session/missing/results").status_code == 404


class TestBoSDirectoryEndpoints:
    def test_list_games_includes_bos(self, fake_db):
        client = TestClient(app)
        slugs = [g["slug"] for g in client.get("/games").json()]
        assert "battle_of_the_sexes" in slugs

    def test_game_details(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/battle_of_the_sexes")
        assert response.status_code == 200
        assert response.json()["name"] == "Battle of the Sexes"

    def test_metrics_declaration(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/battle_of_the_sexes/metrics").status_code == 200

    def test_prompts(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/battle_of_the_sexes/prompts").status_code == 200
