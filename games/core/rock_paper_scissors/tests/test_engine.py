import pytest
from games.core.rock_paper_scissors.config import RPSExperimentConfig, config_from_dict
from games.core.rock_paper_scissors.engine import RPSGame, RPSState


def make_game(rounds: int = 3) -> RPSGame:
    cfg = config_from_dict({"game": "rock_paper_scissors", "variant": "classic", "players": 2, "rounds": rounds})
    return RPSGame.from_config(cfg)


# ── Config ────────────────────────────────────────────────────────────────────

def test_config_from_dict():
    cfg = config_from_dict({"game": "rock_paper_scissors", "variant": "classic", "players": 2, "rounds": 5})
    assert cfg.rounds == 5
    assert cfg.player_ids() == ["A", "B"]


def test_config_hash_is_deterministic():
    cfg1 = config_from_dict({"game": "rock_paper_scissors", "rounds": 10})
    cfg2 = config_from_dict({"game": "rock_paper_scissors", "rounds": 10})
    assert cfg1.config_hash() == cfg2.config_hash()


def test_config_rejects_unknown_variant():
    with pytest.raises(ValueError, match="variant"):
        config_from_dict({"game": "rock_paper_scissors", "variant": "blitz", "rounds": 5})


# ── Initial state ─────────────────────────────────────────────────────────────

def test_initial_state():
    game = make_game()
    state = game.initial_state()
    assert state.round_number == 1
    assert state.phase == "awaiting_action"
    assert set(state.awaiting) == {"A", "B"}
    assert state.total_scores == {"A": 0.0, "B": 0.0}
    assert state.history == []


# ── Single action ─────────────────────────────────────────────────────────────

def test_first_action_still_awaiting():
    game = make_game()
    state = game.initial_state()
    state = game.apply_action(state, "A", "rock")
    assert "A" not in state.awaiting
    assert "B" in state.awaiting
    assert state.phase == "awaiting_action"
    assert state.round_number == 1


# ── Round outcomes ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("a, b, winner, score_a, score_b", [
    ("rock", "scissors", "A", 1.0, -1.0),
    ("scissors", "paper", "A", 1.0, -1.0),
    ("paper", "rock", "A", 1.0, -1.0),
    ("scissors", "rock", "B", -1.0, 1.0),
    ("rock", "rock", "Tie", 0.0, 0.0),
    ("paper", "paper", "Tie", 0.0, 0.0),
    ("scissors", "scissors", "Tie", 0.0, 0.0),
])
def test_round_outcomes(a, b, winner, score_a, score_b):
    game = make_game(rounds=1)
    state = game.initial_state()
    state = game.apply_action(state, "A", a)
    state = game.apply_action(state, "B", b)
    assert state.history[0]["winner"] == winner
    assert state.history[0]["scores"]["A"] == score_a
    assert state.history[0]["scores"]["B"] == score_b


# ── Multi-round ───────────────────────────────────────────────────────────────

def test_scores_accumulate_across_rounds():
    game = make_game(rounds=2)
    state = game.initial_state()
    state = game.apply_action(state, "A", "rock")
    state = game.apply_action(state, "B", "scissors")
    state = game.apply_action(state, "A", "paper")
    state = game.apply_action(state, "B", "scissors")
    assert state.total_scores["A"] == 0.0  # +1 -1
    assert state.total_scores["B"] == 0.0  # -1 +1


def test_game_completes_after_all_rounds():
    game = make_game(rounds=2)
    state = game.initial_state()
    for _ in range(2):
        state = game.apply_action(state, "A", "rock")
        state = game.apply_action(state, "B", "scissors")
    assert game.is_terminal(state)
    assert state.phase == "complete"
    assert len(state.history) == 2


# ── Results ───────────────────────────────────────────────────────────────────

def test_compute_results_winner():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = game.apply_action(state, "A", "rock")
    state = game.apply_action(state, "B", "scissors")
    results = game.compute_results(state)
    assert results["winner"] == "A"
    assert "metrics" in results
    assert "total_payoff" in results["metrics"]


def test_compute_results_raises_if_not_terminal():
    game = make_game(rounds=3)
    state = game.initial_state()
    with pytest.raises(ValueError, match="not complete"):
        game.compute_results(state)


def test_tie_result():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = game.apply_action(state, "A", "rock")
    state = game.apply_action(state, "B", "rock")
    results = game.compute_results(state)
    assert results["winner"] == "Tie"


# ── Validation ────────────────────────────────────────────────────────────────

def test_invalid_move_raises():
    game = make_game()
    state = game.initial_state()
    with pytest.raises(ValueError):
        game.apply_action(state, "A", "lizard")


def test_invalid_player_raises():
    game = make_game()
    state = game.initial_state()
    with pytest.raises(ValueError):
        game.apply_action(state, "C", "rock")


def test_double_submit_raises():
    game = make_game()
    state = game.initial_state()
    state = game.apply_action(state, "A", "rock")
    with pytest.raises(ValueError):
        game.apply_action(state, "A", "paper")


# ── Public state ──────────────────────────────────────────────────────────────

def test_public_state_keys():
    cfg = config_from_dict({"game": "rock_paper_scissors", "rounds": 5})
    game = RPSGame.from_config(cfg)
    state = game.initial_state()
    ps = game.public_state(state, cfg, "sess-1", "hash-1")
    assert ps["phase"] == "awaiting_action"
    assert ps["round"] == 1
    assert ps["round_total"] == 5


# ── Forfeit ───────────────────────────────────────────────────────────────────

def test_forfeit_round():
    game = make_game(rounds=2)
    state = game.initial_state()
    state = game.forfeit_round(state, "A")
    assert state.total_scores["B"] == 1.0
    assert state.total_scores["A"] == -1.0
    assert state.history[0]["forfeit"] is True
    assert state.history[0]["forfeit_by"] == "A"


# ── State serialisation ───────────────────────────────────────────────────────

def test_state_from_dict_round_trip():
    game = make_game(rounds=3)
    state = game.initial_state()
    state = game.apply_action(state, "A", "rock")
    state = game.apply_action(state, "B", "scissors")
    d = {
        "round_number": state.round_number,
        "phase": state.phase,
        "awaiting": state.awaiting,
        "pending_actions": state.pending_actions,
        "history": state.history,
        "total_scores": state.total_scores,
    }
    restored = game.state_from_dict(d)
    assert restored.round_number == state.round_number
    assert restored.total_scores == state.total_scores
