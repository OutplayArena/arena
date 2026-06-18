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


def _valid_payload(**kw):
    payload: dict = {
        "game": "centipede",
        "players": 2,
        "max_steps": 6,
        "seed": 42,
    }
    payload.update(kw)
    return payload


class TestCentipedeConfig:
    def test_config_from_request_defaults(self):
        config = config_from_request(_valid_payload())
        assert config.game == "centipede"
        assert config.max_steps == 6
        assert config.initial_pot_a == 4.0
        assert config.initial_pot_b == 1.0
        assert config.growth_factor == 2.0

    def test_config_rejects_wrong_player_count(self):
        with pytest.raises(ValueError, match="2 players"):
            config_from_request(_valid_payload(players=3))

    def test_config_rejects_max_steps_below_2(self):
        with pytest.raises(ValueError, match="max_steps"):
            config_from_request(_valid_payload(max_steps=1))

    def test_config_rejects_growth_factor_lte_1(self):
        with pytest.raises(ValueError, match="growth_factor"):
            config_from_request(_valid_payload(growth_factor=1.0))

    def test_config_hash_stable(self):
        cfg1 = config_from_request(_valid_payload(seed=13))
        cfg2 = config_from_request(_valid_payload(seed=13))
        assert cfg1.config_hash() == cfg2.config_hash()


class TestCentipedeExperimentCreation:
    def test_create_returns_session_and_tokens(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["config_hash"].startswith("sha256:")
        assert set(data["player_tokens"]) == {"A", "B"}
        assert data["session_id"] in fake_db._store

    def test_create_rejects_invalid_growth_factor(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(growth_factor=0.5))
        assert response.status_code == 400

    def test_create_with_custom_steps(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(max_steps=4))
        assert response.status_code == 200


class TestCentipedeState:
    def test_initial_state_a_acts_first(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["current_player"] == "A"
        assert state["awaiting"] == ["A"]
        assert state["step"] == 1

    def test_initial_state_shows_pots(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        state = client.get(f"/session/{created['session_id']}/state").json()
        assert state["pot_a"] == pytest.approx(4.0)
        assert state["pot_b"] == pytest.approx(1.0)


class TestCentipedeActionSubmission:
    def test_take_on_step_1_ends_game(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]

        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "take"},
        )
        assert response.status_code == 200
        state = response.json()
        assert state.get("game_ended_by") == "A" or state.get("awaiting") == []

    def test_pass_switches_player(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]

        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "pass"},
        )
        assert response.status_code == 200
        state = response.json()
        assert state["current_player"] == "B"
        assert state["awaiting"] == ["B"]

    def test_wrong_player_returns_error(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_b = created["player_tokens"]["B"]

        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"allocation": "take"},
        )
        assert response.status_code in (400, 409)

    def test_invalid_action_returns_400(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]

        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "fold"},
        )
        assert response.status_code == 400

    def test_pass_doubles_pots(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]

        response = client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "pass"},
        )
        state = response.json()
        assert state["pot_a"] == pytest.approx(8.0)
        assert state["pot_b"] == pytest.approx(2.0)


class TestCentipedeResults:
    def test_take_at_step_1(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]

        client.post(
            f"/session/{sid}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": "take"},
        )

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        body = results.json()
        assert body["winner"] == "A"
        m = body["metrics"]
        assert m["take_step"] == 1
        assert m["game_ended_early"] is True

    def test_all_pass_forced_payout(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload(max_steps=4)).json()
        sid = created["session_id"]
        token_a = created["player_tokens"]["A"]
        token_b = created["player_tokens"]["B"]

        player_order = [("A", token_a), ("B", token_b), ("A", token_a), ("B", token_b)]
        for _, token in player_order:
            client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token}"},
                json={"allocation": "pass"},
            )

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        m = results.json()["metrics"]
        assert m["game_ended_early"] is False
        assert m["take_step"] is None

    def test_results_before_completion_returns_409(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/results")
        assert response.status_code == 409

    def test_unknown_session_returns_404(self, fake_db):
        client = TestClient(app)
        assert client.get("/session/missing/results").status_code == 404


class TestCentipedeDirectoryEndpoints:
    def test_list_games_includes_centipede(self, fake_db):
        client = TestClient(app)
        slugs = [g["slug"] for g in client.get("/games").json()]
        assert "centipede" in slugs

    def test_game_details(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/centipede")
        assert response.status_code == 200
        assert response.json()["name"] == "Centipede Game"

    def test_metrics_declaration(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/centipede/metrics").status_code == 200

    def test_prompts(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/centipede/prompts").status_code == 200
