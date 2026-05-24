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


def test_create_session_starts_awaiting_both_players():
    config = make_config()

    session = GameSession.create(config)

    assert session.session_id
    assert session.config == config
    assert session.config_hash == config.config_hash()
    assert session.round_number == 1
    assert session.phase == "awaiting_action"
    assert session.awaiting == ["A", "B"]
    assert session.pending_actions == {}
    assert session.history == []
    assert session.total_scores == {"A": 0, "B": 0}


def test_public_state_is_json_like():
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


def test_submit_first_action_does_not_resolve_round():
    session = GameSession.create(make_config())

    session.submit_action("A", [10, 0, 0])

    assert session.awaiting == ["B"]
    assert session.pending_actions == {"A": [10, 0, 0]}
    assert session.history == []
    assert session.phase == "awaiting_action"
    assert session.round_number == 1


def test_submit_second_action_resolves_round_and_advances():
    session = GameSession.create(make_config(rounds=2))

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 10, 0])

    assert session.round_number == 2
    assert session.phase == "awaiting_action"
    assert session.awaiting == ["A", "B"]
    assert session.pending_actions == {}
    assert session.total_scores == {"A": 1.5, "B": 1.5}
    assert session.history == [
        {
            "round": 1,
            "allocations": {"A": [10, 0, 0], "B": [0, 10, 0]},
            "scores": {"A": 1.5, "B": 1.5},
            "winner": "Tie",
            "total_scores": {"A": 1.5, "B": 1.5},
        }
    ]


def test_session_completes_after_final_round():
    session = GameSession.create(make_config(rounds=1))

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 10, 0])

    assert session.phase == "complete"
    assert session.round_number == 1
    assert session.awaiting == []
    assert session.pending_actions == {}
    assert len(session.history) == 1


def test_results_are_available_only_when_complete():
    session = GameSession.create(make_config(rounds=1))

    with pytest.raises(ValueError, match="complete"):
        session.results()

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 10, 0])

    assert session.results() == {
        "session_id": session.session_id,
        "config_hash": session.config_hash,
        "total_scores": {"A": 1.5, "B": 1.5},
        "winner": "Tie",
        "history": session.history,
    }


def test_results_report_winner():
    session = GameSession.create(make_config(rounds=1))

    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 5, 5])

    assert session.results()["winner"] == "B"
    assert session.results()["total_scores"] == {"A": 1, "B": 2}


def test_rejects_duplicate_action():
    session = GameSession.create(make_config())

    session.submit_action("A", [10, 0, 0])

    with pytest.raises(ValueError, match="already submitted"):
        session.submit_action("A", [0, 10, 0])


def test_rejects_unknown_player():
    session = GameSession.create(make_config())

    with pytest.raises(ValueError, match="unknown player"):
        session.submit_action("C", [10, 0, 0])


def test_rejects_invalid_allocation():
    session = GameSession.create(make_config())

    with pytest.raises(ValueError, match="invalid action"):
        session.submit_action("A", [10, 0])

    with pytest.raises(ValueError, match="invalid action"):
        session.submit_action("A", [9, 0, 0])


def test_rejects_actions_after_completion():
    session = GameSession.create(make_config(rounds=1))
    session.submit_action("A", [10, 0, 0])
    session.submit_action("B", [0, 10, 0])

    with pytest.raises(ValueError, match="already complete"):
        session.submit_action("A", [10, 0, 0])
