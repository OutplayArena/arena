import os

os.environ["API_PREFIX"] = ""
os.environ["GITHUB_CLIENT_ID"] = ""
os.environ["GITHUB_CLIENT_SECRET"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["ENABLE_AGENT_REST_API"] = "true"

import pytest
from fastapi.testclient import TestClient

from nash_arena.main import app, config_from_request, get_broker
from nash_arena.db import get_db
from nash_arena.auth.dependencies import require_user, _ensure_local_user


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
        "game": "stag_hunt",
        "variant": "classic",
        "players": 2,
        "rounds": rounds,
        "seed": 42,
    }
    payload.update(kw)
    return payload


class TestSHConfig:
    def test_config_from_request_builds_sh_config(self):
        config = config_from_request(_valid_payload())
        assert config.game == "stag_hunt"
        assert config.rounds == 3
        assert config.payoff_stag_stag == 4.0
        assert config.payoff_hare_hare == 2.0
        assert config.payoff_stag_hare == 0.0

    def test_config_rejects_invalid_payoff_order(self):
        payload = _valid_payload(payoff_stag_stag=1.0, payoff_hare_hare=4.0)
        with pytest.raises(ValueError, match="stag_stag > hare_hare"):
            config_from_request(payload)

    def test_config_rejects_invalid_noise(self):
        payload = _valid_payload(variant="noisy", noise=0.9)
        with pytest.raises(ValueError, match="noise"):
            config_from_request(payload)

    def test_config_rejects_wrong_player_count(self):
        payload = _valid_payload(players=3)
        with pytest.raises(ValueError, match="2 players"):
            config_from_request(payload)

    def test_config_hash_stable(self):
        cfg1 = config_from_request(_valid_payload(seed=7))
        cfg2 = config_from_request(_valid_payload(seed=7))
        assert cfg1.config_hash() == cfg2.config_hash()


class TestSHExperimentCreation:
    def test_create_returns_session_and_tokens(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["config_hash"].startswith("sha256:")
        assert set(data["player_tokens"]) == {"A", "B"}
        assert data["session_id"] in fake_db._store

    def test_create_rejects_invalid_payoffs(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(payoff_stag_stag=1.0, payoff_hare_hare=4.0))
        assert response.status_code == 400

    def test_create_noisy_variant(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(variant="noisy", noise=0.1))
        assert response.status_code == 200


class TestSHState:
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

    def test_state_includes_payoff_structure(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        state = client.get(f"/session/{created['session_id']}/state").json()
        assert "payoffs" in state
        assert state["payoffs"]["stag_stag"] == 4.0


class TestSHActionSubmission:
    def test_submit_first_action_awaits_second(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "stag"},
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
            json={"allocation": "cooperate"},
        )
        assert response.status_code == 400

    def test_duplicate_action_returns_conflict(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "stag"},
        )
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "hare"},
        )
        assert response.status_code == 409


class TestSHResults:
    def test_mutual_stag_cooperation(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        for _ in range(3):
            client.post(f"/session/{sid}/action",
                        headers={"Authorization": f"Bearer {token_a}"},
                        json={"allocation": "stag"})
            client.post(f"/session/{sid}/action",
                        headers={"Authorization": f"Bearer {token_b}"},
                        json={"allocation": "stag"})

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        body = results.json()
        assert body["winner"] == "Tie"
        m = body["metrics"]
        assert m["stag_rate"]["A"] == pytest.approx(1.0)
        assert m["mutual_stag_rate"] == pytest.approx(1.0)

    def test_results_before_completion_returns_409(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/results")
        assert response.status_code == 409

    def test_unknown_session_returns_404(self, fake_db):
        client = TestClient(app)
        assert client.get("/session/missing/results").status_code == 404


class TestSHDirectoryEndpoints:
    def test_list_games_includes_stag_hunt(self, fake_db):
        client = TestClient(app)
        slugs = [g["slug"] for g in client.get("/games").json()]
        assert "stag_hunt" in slugs

    def test_game_details(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/stag_hunt")
        assert response.status_code == 200
        assert response.json()["name"] == "Stag Hunt"

    def test_metrics_declaration(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/stag_hunt/metrics").status_code == 200

    def test_prompts(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/stag_hunt/prompts").status_code == 200
