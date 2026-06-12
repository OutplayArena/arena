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


def _valid_payload(rounds=2, players=4, **kw):
    payload: dict = {
        "game": "public_goods",
        "variant": "classic",
        "players": players,
        "rounds": rounds,
        "seed": 42,
    }
    payload.update(kw)
    return payload


class TestPGGConfig:
    def test_config_from_request_defaults(self):
        config = config_from_request(_valid_payload())
        assert config.game == "public_goods"
        assert config.rounds == 2
        assert config.players == 4
        assert config.endowment == 10.0
        assert config.multiplier == 2.0

    def test_config_rejects_too_few_players(self):
        with pytest.raises(ValueError, match="3–6 players"):
            config_from_request(_valid_payload(players=2))

    def test_config_rejects_too_many_players(self):
        with pytest.raises(ValueError, match="3–6 players"):
            config_from_request(_valid_payload(players=7))

    def test_config_accepts_3_players(self):
        config = config_from_request(_valid_payload(players=3))
        assert config.player_ids() == ["A", "B", "C"]

    def test_config_accepts_6_players(self):
        config = config_from_request(_valid_payload(players=6))
        assert len(config.player_ids()) == 6

    def test_config_rejects_low_multiplier(self):
        with pytest.raises(ValueError, match="multiplier"):
            config_from_request(_valid_payload(multiplier=0.5))

    def test_config_punishment_variant(self):
        config = config_from_request(_valid_payload(variant="punishment"))
        assert config.variant == "punishment"

    def test_config_hash_stable(self):
        cfg1 = config_from_request(_valid_payload(seed=3))
        cfg2 = config_from_request(_valid_payload(seed=3))
        assert cfg1.config_hash() == cfg2.config_hash()


class TestPGGExperimentCreation:
    def test_create_returns_session_and_tokens(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["config_hash"].startswith("sha256:")
        assert set(data["player_tokens"]) == {"A", "B", "C", "D"}
        assert data["session_id"] in fake_db._store

    def test_create_3_player_game(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(players=3))
        assert response.status_code == 200
        data = response.json()
        assert set(data["player_tokens"]) == {"A", "B", "C"}

    def test_create_rejects_too_few_players(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(players=2))
        assert response.status_code == 400

    def test_create_punishment_variant(self, fake_db):
        client = TestClient(app)
        response = client.post("/experiment", json=_valid_payload(variant="punishment"))
        assert response.status_code == 200


class TestPGGState:
    def test_state_returns_public_state(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["session_id"] == created["session_id"]
        assert state["round"] == 1
        assert state["round_total"] == 2
        assert sorted(state["awaiting"]) == ["A", "B", "C", "D"]

    def test_state_includes_endowment(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        state = client.get(f"/session/{created['session_id']}/state").json()
        assert "endowment" in state or "multiplier" in state or "params" in state


class TestPGGActionSubmission:
    def test_submit_first_action_still_awaiting_others(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 5.0},
        )
        assert response.status_code == 200
        awaiting = response.json()["awaiting"]
        assert "A" not in awaiting
        assert len(awaiting) == 3

    def test_submit_above_endowment_returns_400(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 15.0},
        )
        assert response.status_code == 400

    def test_submit_negative_contribution_returns_400(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": -1.0},
        )
        assert response.status_code == 400

    def test_duplicate_action_returns_conflict(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        token_a = created["player_tokens"]["A"]
        client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 5.0},
        )
        response = client.post(
            f"/session/{created['session_id']}/action",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"allocation": 8.0},
        )
        assert response.status_code == 409


class TestPGGResults:
    def _complete_round(self, client, sid, tokens, contribution):
        for player, token in tokens.items():
            client.post(
                f"/session/{sid}/action",
                headers={"Authorization": f"Bearer {token}"},
                json={"allocation": contribution},
            )

    def test_all_max_contribution(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        tokens = created["player_tokens"]

        for _ in range(2):
            self._complete_round(client, sid, tokens, 10.0)

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        m = results.json()["metrics"]
        assert m["avg_contribution"]["A"] == pytest.approx(10.0)
        assert m["free_rider_count"] == 0

    def test_all_free_ride(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        sid = created["session_id"]
        tokens = created["player_tokens"]

        for _ in range(2):
            self._complete_round(client, sid, tokens, 0.0)

        results = client.get(f"/session/{sid}/results")
        assert results.status_code == 200
        m = results.json()["metrics"]
        assert m["avg_contribution"]["A"] == pytest.approx(0.0)
        assert m["free_rider_count"] == 4

    def test_results_before_completion_returns_409(self, fake_db):
        client = TestClient(app)
        created = client.post("/experiment", json=_valid_payload()).json()
        response = client.get(f"/session/{created['session_id']}/results")
        assert response.status_code == 409

    def test_unknown_session_returns_404(self, fake_db):
        client = TestClient(app)
        assert client.get("/session/missing/results").status_code == 404


class TestPGGDirectoryEndpoints:
    def test_list_games_includes_pgg(self, fake_db):
        client = TestClient(app)
        slugs = [g["slug"] for g in client.get("/games").json()]
        assert "public_goods" in slugs

    def test_game_details(self, fake_db):
        client = TestClient(app)
        response = client.get("/games/public_goods")
        assert response.status_code == 200
        assert response.json()["name"] == "Public Goods Game"

    def test_metrics_declaration(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/public_goods/metrics").status_code == 200

    def test_prompts(self, fake_db):
        client = TestClient(app)
        assert client.get("/games/public_goods/prompts").status_code == 200
