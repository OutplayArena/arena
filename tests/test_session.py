import pytest

from games.core.blotto.config import BattlefieldConfig, BlottoExperimentConfig
from nash_arena.auth import create_player_token, decode_token
from nash_arena.experiment_config import ExperimentRuntimeConfig, WandbConfig
from nash_arena.session import GameSession


def make_config(rounds=2):
    return BlottoExperimentConfig(
        game="blotto",
        variant="classic",
        players=2,
        budget=[10, 10],
        battlefields=[
            BattlefieldConfig(id="A", value=1.0),
            BattlefieldConfig(id="B", value=1.0),
            BattlefieldConfig(id="C", value=1.0),
        ],
        rounds=rounds,
        seed=42,
    )


class FakeRoundLogger:
    def __init__(self):
        self.round_logs = []
        self.terminal_logs = []
        self.finished = False

    def log_round(self, payload, step):
        self.round_logs.append({"payload": payload, "step": step})

    def log_terminal(self, payload):
        self.terminal_logs.append(payload)

    def finish(self):
        self.finished = True


def test_create_session_stores_game_and_initial_state():
    config = make_config()

    session = GameSession.create(config)

    assert session.session_id
    assert session.config == config
    assert session.config_hash == config.config_hash()
    assert session.game.num_battlefields == 3
    assert session.game.total_resources == 10
    assert session.game.num_rounds == 2
    assert session.state.round_number == 1
    assert session.state.phase == "awaiting_action"
    assert session.state.awaiting == ["A", "B"]
    assert set(session.player_tokens) == {"A", "B"}
    assert session.player_tokens["A"]
    assert session.player_tokens["B"]
    assert session.player_tokens["A"] != session.player_tokens["B"]
    assert session.player_tokens["A"].count(".") == 2
    assert session.wandb_logger is None


def test_create_session_with_wandb_starts_logger(monkeypatch):
    started = []

    class FakeLogger:
        def __init__(self, wandb_config, game_config, encrypted_api_key):
            self.wandb_config = wandb_config
            self.game_config = game_config
            self.encrypted_api_key = encrypted_api_key

        def start(self):
            started.append(self)
            return self

    monkeypatch.setenv(
        "NASH_ARENA_WANDB_ENCRYPTION_KEY",
        "0" * 64,
    )
    monkeypatch.setattr("nash_arena.session.WandbGameLogger", FakeLogger)
    runtime_config = ExperimentRuntimeConfig(
        wandb=WandbConfig(
            api_key="wandb-secret",
            project="arena-runs",
        )
    )

    session = GameSession.create(make_config(), runtime_config=runtime_config)

    assert session.wandb_logger is started[0]
    assert session.wandb_logger.wandb_config == runtime_config.wandb
    assert session.wandb_logger.game_config == session.config
    assert "wandb-secret" not in session.wandb_logger.encrypted_api_key


def test_public_state_reads_from_game_state():
    config = make_config(rounds=3)
    session = GameSession.create(config)

    state = session.public_state()

    assert state == {
        "session_id": session.session_id,
        "config_hash": config.config_hash(),
        "round": 1,
        "round_total": 3,
        "phase": "awaiting_action",
        "awaiting": ["A", "B"],
        "battlefields": [
            {"id": "A", "value": 1.0},
            {"id": "B", "value": 1.0},
            {"id": "C", "value": 1.0},
        ],
        "budgets": {"A": 10, "B": 10},
        "total_scores": {"A": 0, "B": 0},
        "history": [],
    }
    assert "player_tokens" not in state


def test_submit_action_delegates_to_engine_state_machine():
    session = GameSession.create(make_config(rounds=2))

    session.submit_action("A", [10, 0, 0])

    assert session.state.awaiting == ["B"]
    assert session.state.pending_actions == {"A": [10, 0, 0]}
    assert session.state.history == []

    session.submit_action("B", [0, 10, 0])

    assert session.state.round_number == 2
    assert session.state.awaiting == ["A", "B"]
    assert session.state.pending_actions == {}
    assert session.state.total_scores == {"A": 1.5, "B": 1.5}
    assert len(session.state.history) == 1


def test_submit_action_without_wandb_logger_does_not_crash():
    session = GameSession.create(make_config(rounds=1))

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])

    assert session.state.phase == "complete"
    assert session.wandb_finished is False


def test_submit_action_does_not_log_before_round_resolves():
    session = GameSession.create(make_config(rounds=1))
    fake_logger = FakeRoundLogger()
    session.wandb_logger = fake_logger

    session.submit_action("A", [10, 0, 0])

    assert fake_logger.round_logs == []


def test_submit_action_logs_resolved_round_to_wandb_once():
    session = GameSession.create(make_config(rounds=1))
    fake_logger = FakeRoundLogger()
    session.wandb_logger = fake_logger

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])

    assert fake_logger.round_logs == [
        {
            "step": 1,
            "payload": {
                "round": 1,
                "scores/A": 1,
                "scores/B": 2,
                "total_scores/A": 1,
                "total_scores/B": 2,
                "winner": "B",
                "allocation_concentration/A": 1.0,
                "allocation_concentration/B": 0.5,
            },
        }
    ]
    assert fake_logger.finished is True


def test_submit_action_logs_each_resolved_round_once():
    session = GameSession.create(make_config(rounds=2))
    fake_logger = FakeRoundLogger()
    session.wandb_logger = fake_logger

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])
    session.submit_action("A", [0, 10, 0])
    session.submit_action("B", [0, 5, 5])

    assert [entry["step"] for entry in fake_logger.round_logs] == [1, 2]
    assert [entry["payload"]["round"] for entry in fake_logger.round_logs] == [1, 2]


def test_submit_action_logs_terminal_metrics_and_finishes_wandb():
    session = GameSession.create(make_config(rounds=1))
    fake_logger = FakeRoundLogger()
    session.wandb_logger = fake_logger

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])

    assert fake_logger.terminal_logs == [
        {
            "final/winner": "B",
            "final/total_scores/A": 1,
            "final/total_scores/B": 2,
            "metrics/average_payoff/A": 1.0,
            "metrics/average_payoff/B": 2.0,
            "metrics/round_win_rate/A": 0.0,
            "metrics/round_win_rate/B": 1.0,
            "metrics/round_win_rate/Tie": 0.0,
        }
    ]
    assert fake_logger.finished is True
    assert session.wandb_finished is True


def test_terminal_wandb_logging_is_idempotent():
    session = GameSession.create(make_config(rounds=1))
    fake_logger = FakeRoundLogger()
    session.wandb_logger = fake_logger

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])
    session._log_terminal_to_wandb()

    assert len(fake_logger.terminal_logs) == 1


def test_session_results_add_session_metadata():
    session = GameSession.create(make_config(rounds=1))

    with pytest.raises(ValueError, match="complete"):
        session.results()

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])

    assert session.results() == {
        "session_id": session.session_id,
        "config_hash": session.config_hash,
        "total_scores": {"A": 1, "B": 2},
        "winner": "B",
        "history": session.state.history,
        "metrics": {
            "total_payoff": {"A": 1, "B": 2},
            "average_payoff": {"A": 1.0, "B": 2.0},
            "round_win_counts": {"A": 0, "B": 1, "Tie": 0},
            "round_win_rate": {"A": 0.0, "B": 1.0, "Tie": 0.0},
            "allocation_concentration": {"A": 1.0, "B": 0.5},
        },
    }


def test_session_rejects_invalid_and_duplicate_actions_via_engine():
    session = GameSession.create(make_config(rounds=1))

    with pytest.raises(ValueError, match="unknown player"):
        session.submit_action("C", [10, 0, 0])

    with pytest.raises(ValueError, match="invalid action"):
        session.submit_action("A", [10, 0])

    session.submit_action("A", [10, 0, 0])

    with pytest.raises(ValueError, match="already submitted"):
        session.submit_action("A", [0, 10, 0])

    session.submit_action("B", [0, 10, 0])

    with pytest.raises(ValueError, match="already complete"):
        session.submit_action("A", [10, 0, 0])


def test_creation_response_includes_scoped_player_tokens():
    session = GameSession.create(make_config())

    assert session.creation_response() == {
        "session_id": session.session_id,
        "config_hash": session.config_hash,
        "player_tokens": session.player_tokens,
    }


def test_player_for_token_resolves_player_identity():
    session = GameSession.create(make_config())

    assert session.player_for_token(session.player_tokens["A"]) == "A"
    assert session.player_for_token(session.player_tokens["B"]) == "B"


def test_player_tokens_include_signed_session_claims():
    session = GameSession.create(make_config())

    claims = decode_token(session.player_tokens["A"])

    assert claims["session_id"] == session.session_id
    assert claims["player"] == "A"
    assert claims["scope"] == "game:action"
    assert claims["exp"] > claims["iat"]


def test_player_token_from_another_session_is_rejected():
    session = GameSession.create(make_config())
    other_session_token = create_player_token(session_id="other-session", player="A")

    with pytest.raises(ValueError, match="invalid player token"):
        session.player_for_token(other_session_token)


def test_invalid_player_token_is_rejected():
    session = GameSession.create(make_config())

    with pytest.raises(ValueError, match="invalid player token"):
        session.player_for_token("bad-token")


def test_submit_action_with_token_uses_token_identity():
    session = GameSession.create(make_config(rounds=2))

    session.submit_action_with_token(session.player_tokens["A"], [10, 0, 0])

    assert session.state.awaiting == ["B"]
    assert session.state.pending_actions == {"A": [10, 0, 0]}

    session.submit_action_with_token(session.player_tokens["B"], [0, 10, 0])

    assert session.state.round_number == 2
    assert session.state.pending_actions == {}
    assert session.state.total_scores == {"A": 1.5, "B": 1.5}


def test_submit_action_with_token_rejects_invalid_and_duplicate_tokens():
    session = GameSession.create(make_config())
    token_a = session.player_tokens["A"]

    with pytest.raises(ValueError, match="invalid player token"):
        session.submit_action_with_token("bad-token", [10, 0, 0])

    session.submit_action_with_token(token_a, [10, 0, 0])

    with pytest.raises(ValueError, match="already submitted"):
        session.submit_action_with_token(token_a, [0, 10, 0])
