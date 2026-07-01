import pytest

from games.core.colonelblotto.config import BattlefieldConfig, ColonelBlottoExperimentConfig
from arena.session import GameSession


def make_config(rounds=2):
    return ColonelBlottoExperimentConfig(
        game="colonelblotto",
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


def test_public_state_reads_from_game_state():
    config = make_config(rounds=3)
    session = GameSession.create(config)

    state = session.public_state()

    assert state == {
        "session_id": session.session_id,
        "config_hash": config.config_hash(),
        "config": config.to_dict(),
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
        "messages": [],
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


def test_build_wandb_round_payloads_returns_one_entry_per_resolved_round():
    session = GameSession.create(make_config(rounds=2))

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])
    session.submit_action("A", [0, 10, 0])
    session.submit_action("B", [0, 5, 5])

    payloads = session.build_wandb_round_payloads()

    assert len(payloads) == 2
    assert [step for _, step in payloads] == [1, 2]
    assert [p["round"] for p, _ in payloads] == [1, 2]


def test_build_wandb_round_payloads_contains_scores_and_concentration():
    session = GameSession.create(make_config(rounds=1))

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])

    payloads = session.build_wandb_round_payloads()

    assert len(payloads) == 1
    payload, step = payloads[0]
    assert step == 1
    assert payload["scores/A"] == 1
    assert payload["scores/B"] == 2
    assert payload["total_scores/A"] == 1
    assert payload["total_scores/B"] == 2
    assert payload["winner"] == "B"
    assert payload["allocation_concentration/A"] == 1.0
    assert payload["allocation_concentration/B"] == 0.5


def test_build_wandb_terminal_payload_contains_final_and_rich_metrics():
    session = GameSession.create(make_config(rounds=1))

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])

    payload = session.build_wandb_terminal_payload()

    assert payload["final/winner"] == "B"
    assert payload["final/total_scores/A"] == 1
    assert payload["final/total_scores/B"] == 2
    assert payload["metrics/average_payoff/A"] == 1.0
    assert payload["metrics/average_payoff/B"] == 2.0
    assert payload["metrics/round_win_rate/A"] == 0.0
    assert payload["metrics/round_win_rate/B"] == 1.0
    assert payload["metrics/round_win_rate/Tie"] == 0.0
    assert payload["rich/A/total_payoff"] == 1.0
    assert payload["rich/A/behavioral_consistency"] == 1.0
    assert payload["rich/B/total_payoff"] == 2.0
    assert payload["rich/joint/gini_coefficient"] == 0.1667


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

    resp = session.creation_response()
    assert resp["session_id"] == session.session_id
    assert resp["config_hash"] == session.config_hash
    assert resp["config"] == session.config.to_dict()
    assert resp["player_tokens"] == session.player_tokens
    assert "arena_version" in resp


def test_player_for_token_resolves_player_identity():
    session = GameSession.create(make_config())

    assert session.player_for_token(session.player_tokens["A"]) == "A"
    assert session.player_for_token(session.player_tokens["B"]) == "B"


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
