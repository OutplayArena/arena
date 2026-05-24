import pytest

from blotto.config import BattlefieldConfig, BlottoExperimentConfig
from blotto.session import GameSession


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
