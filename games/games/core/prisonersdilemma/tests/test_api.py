import os

os.environ["API_PREFIX"] = ""
os.environ["GITHUB_CLIENT_ID"] = ""
os.environ["GITHUB_CLIENT_SECRET"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["ENABLE_AGENT_REST_API"] = "true"

import pytest
from fastapi.testclient import TestClient

from arena.main import app, config_from_request, get_broker
from arena.db import get_db
from arena.auth.dependencies import require_user, _ensure_local_user


class FakeBroker:
    def __init__(self, db=None):
        self._db = db
        self._cache = {}

    async def publish(self, channel, message):
        pass

    async def cache_get(self, key):
        return self._cache.get(key)

    async def cache_set(self, key, value, ttl=None):
        self._cache[key] = value

    async def enqueue(self, queue, message):
        if queue == "state:persist" and self._db:
            session_id = message.get("session_id")
            if session_id and session_id in self._db._store:
                row = self._db._store[session_id]
                row.state_json = message.get("state", row.state_json)
                row.status = message.get("status", row.status)
                row.error_message = message.get("error_message")
                row.locked = message.get("locked", row.locked)

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
            raise Exception("No row found")
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
    broker = FakeBroker(db)
    app.dependency_overrides[get_broker] = lambda: broker

    async def _bypass_auth():
        return await _ensure_local_user(db)
    app.dependency_overrides[require_user] = _bypass_auth

    yield db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_broker, None)
    app.dependency_overrides.pop(require_user, None)


@pytest.fixture(autouse=True)
def enable_agent_rest_api():
    os.environ["ENABLE_AGENT_REST_API"] = "true"
    yield


def _valid_payload(rounds=3, **kw):
    payload: dict = {
        "game": "prisonersdilemma",
        "variant": "classic",
        "players": 2,
        "rounds": rounds,
        "seed": 42,
    }
    payload.update(kw)
    return payload


class TestPDConfig:
    def test_config_from_request_builds_pd_config(self):
        config = config_from_request(_valid_payload())
        assert config.game == "prisonersdilemma"
        assert config.rounds == 3
        assert config.payoff_T == 5.0
        assert config.payoff_R == 3.0
        assert config.payoff_P == 1.0
        assert config.payoff_S == 0.0
        assert config.noise == 0.0
        assert config.player_ids() == ["A", "B"]

    def test_config_rejects_invalid_payoff_constraint(self):
        payload = _valid_payload(payoff_T=3.0, payoff_R=3.0)
        with pytest.raises(ValueError, match="T > R"):
            config_from_request(payload)

    def test_config_rejects_invalid_noise(self):
        payload = _valid_payload(variant="noisy", noise=0.6)
        with pytest.raises(ValueError, match="noise"):
            config_from_request(payload)

    def test_config_rejects_invalid_players(self):
        payload = _valid_payload()
        payload["players"] = 3
        with pytest.raises(ValueError, match="2 players"):
            config_from_request(payload)

    def test_config_hash_stable(self):
        cfg1 = config_from_request(_valid_payload(seed=7))
        cfg2 = config_from_request(_valid_payload(seed=7))
        assert cfg1.config_hash() == cfg2.config_hash()

    def test_config_default_scenario_is_prison(self):
        config = config_from_request(_valid_payload())
        assert config.scenario == "prison"

    def test_config_accepts_valid_scenario(self):
        for sid in ["prison", "business", "climate", "arms_race", "roommates"]:
            config = config_from_request(_valid_payload(scenario=sid))
            assert config.scenario == sid

    def test_config_rejects_invalid_scenario(self):
        payload = _valid_payload(scenario="football")
        with pytest.raises(ValueError, match="unknown scenario"):
            config_from_request(payload)

    def test_config_accepts_system_prompt(self):
        config = config_from_request(_valid_payload(system_prompt="Be cooperative."))
        assert config.system_prompt == "Be cooperative."

    def test_config_system_prompt_defaults_to_empty(self):
        config = config_from_request(_valid_payload())
        assert config.system_prompt == ""

    def test_config_get_scenario_returns_scenario_object(self):
        config = config_from_request(_valid_payload(scenario="business"))
        s = config.get_scenario()
        assert s.id == "business"
        assert s.name == "Price War"

    def test_config_to_dict_includes_scenario_and_prompt(self):
        config = config_from_request(_valid_payload(scenario="arms_race", system_prompt="Win!"))
        d = config.to_dict()
        assert d["scenario"] == "arms_race"
        assert d["system_prompt"] == "Win!"


class TestPDExperimentCreation:
    def test_create_experiment_returns_session_and_tokens(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["config_hash"].startswith("sha256:")
        assert set(data["player_tokens"]) == {"A", "B"}
        assert data["player_tokens"]["A"] != data["player_tokens"]["B"]
        assert data["session_id"] in fake_db._store

    def test_create_experiment_rejects_invalid_payoffs(self, fake_db):
        client = TestClient(app)
        payload = _valid_payload(payoff_T=1.0, payoff_R=2.0, payoff_P=0.5, payoff_S=-1.0)
        response = client.post("/experiment", json=payload)
        assert response.status_code == 400
        assert "T > R" in response.json()["detail"]

    def test_create_noisy_variant(self, fake_db):
        client = TestClient(app)
        payload = _valid_payload(variant="noisy", noise=0.2)
        response = client.post("/experiment", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] in fake_db._store

    def test_create_experiment_rejects_invalid_scenario(self, fake_db):
        client = TestClient(app)
        payload = _valid_payload(scenario="invalid_scenario")
        response = client.post("/experiment", json=payload)
        assert response.status_code == 400

    def test_create_experiment_with_business_scenario(self, fake_db):
        client = TestClient(app)
        payload = _valid_payload(scenario="business")
        response = client.post("/experiment", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] in fake_db._store


class TestPDState:
    def test_get_state_returns_public_state(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["session_id"] == created["session_id"]
        assert state["round"] == 1
        assert state["round_total"] == 3

    def test_state_includes_scenario_info(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload(scenario="arms_race")).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert "scenario" in state
        assert state["scenario"]["id"] == "arms_race"
        assert state["scenario"]["name"] == "Arms Race"
        assert "cooperate_label" in state["scenario"]
        assert "defect_label" in state["scenario"]

    def test_state_includes_system_prompt_when_set(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload(system_prompt="Custom prompt!")).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state.get("system_prompt") == "Custom prompt!"

    def test_state_system_prompt_defaults_empty(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state.get("system_prompt") == ""


class TestPDActionSubmission:
    def test_submit_action_rejects_invalid_move(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "rock"},
        )
        assert response.status_code == 400

    def test_submit_first_action_awaits_second(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "cooperate"},
        )
        assert response.status_code == 200
        assert response.json()["awaiting"] == ["B"]

    def test_duplicate_action_returns_conflict(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "cooperate"},
        )
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "defect"},
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
        assert response.json()["history"][-1]["forfeit"] is True


class TestPDResults:
    def test_mutual_cooperation_returns_cooperation_metrics(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        for _ in range(3):
            client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"allocation": "cooperate"},
            )
            client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token_b}"},
                json={"allocation": "cooperate"},
            )

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        body = results.json()
        assert body["winner"] == "Tie"
        assert "metrics" in body
        m = body["metrics"]
        assert "total_payoff" in m
        assert "average_payoff" in m
        assert "cooperation_rate" in m
        assert "mutual_cooperation_rate" in m
        assert "mutual_defection_rate" in m
        assert "outcome_counts" in m
        assert m["cooperation_rate"]["A"] == pytest.approx(1.0)
        assert m["cooperation_rate"]["B"] == pytest.approx(1.0)
        assert m["mutual_cooperation_rate"] == pytest.approx(1.0)
        assert m["outcome_counts"]["CC"] == 3

    def test_always_defect_vs_always_cooperate(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        for _ in range(3):
            client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"allocation": "defect"},
            )
            client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token_b}"},
                json={"allocation": "cooperate"},
            )

        results = client.get(f"/session/{sid}/results")
        body = results.json()
        assert body["winner"] == "A"
        m = body["metrics"]
        assert m["cooperation_rate"]["A"] == pytest.approx(0.0)
        assert m["cooperation_rate"]["B"] == pytest.approx(1.0)
        assert m["mutual_cooperation_rate"] == pytest.approx(0.0)
        assert m["outcome_counts"]["DC"] == 3

    def test_results_before_completion_returns_409(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/results")
        assert response.status_code == 409

    def test_unknown_session_returns_404(self, fake_db):
        client = TestClient(app)
        response = client.get("/session/missing/results")
        assert response.status_code == 404


class TestPDDirectoryEndpoints:
    def test_list_games_includes_pd(self, fake_db):
        client = TestClient(app)
        response = client.get("/games")
        games = response.json()
        slugs = [g["slug"] for g in games]
        assert "prisonersdilemma" in slugs

    def test_pd_game_details(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/prisonersdilemma")
        assert response.status_code == 200
        assert response.json()["name"] == "Prisoner's Dilemma"

    def test_pd_metrics_declaration(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/prisonersdilemma/metrics")
        assert response.status_code == 200
        assert "metrics" in response.json()

    def test_pd_prompts(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/prisonersdilemma/prompts")
        assert response.status_code == 200
        assert response.json()["action_format"]["type"] == "string"
