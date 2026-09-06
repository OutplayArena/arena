"""to_match() must handle Texas Hold'em's per-hand history shape (issue #24):
`hand`/`street_actions`/cumulative `total_scores` instead of the generic
`round`/`actions`/`scores` shape other games use."""
from games.core.texas_hold_em.config import config_from_dict
from arena.metrics.evaluator import MatchEvaluator
from arena.metrics.registry import AgentRegistry
from arena.session import GameSession


def make_holdem_session(rounds=2, players=2):
    cfg = config_from_dict({
        "game": "texas_hold_em", "variant": "classic",
        "players": players, "rounds": rounds, "seed": 1,
    })
    return GameSession.create(cfg, agents={"A": "gpt-5", "B": "granite"})


def test_round_number_falls_back_to_hand_key():
    session = make_holdem_session(rounds=1)
    session.submit_action("A", "fold")
    assert session.state.phase == "complete"

    match = session.to_match()
    assert len(match.moves) > 0
    assert all(m.round_number == 1 for m in match.moves)


def test_actions_derived_from_street_actions():
    session = make_holdem_session(rounds=1)
    session.submit_action("A", "fold")

    match = session.to_match()
    actions_by_agent = {m.agent_id: m.action for m in match.moves}
    # A's fold is the only recorded street action; B never acted.
    assert actions_by_agent.get("gpt-5") == "fold"
    assert "granite" not in actions_by_agent


def test_payoff_is_per_hand_delta_not_cumulative_total():
    session = make_holdem_session(rounds=2)
    session.submit_action("A", "fold")  # hand 1: A folds, B wins the pot
    assert not session.game.is_terminal(session.state)
    session.submit_action("A", "fold")  # hand 2: A folds again

    match = session.to_match()
    a_moves = sorted(
        (m for m in match.moves if m.agent_id == "gpt-5"),
        key=lambda m: m.round_number,
    )
    assert len(a_moves) == 2
    # Each hand's payoff is that hand's own delta, not the running cumulative
    # total_scores (which would double-count across hands if used directly).
    assert a_moves[0].payoff == a_moves[1].payoff


def test_match_evaluator_metrics_are_populated_not_empty():
    """Regression test for the actual #24 symptom: compute_agent/compute_joint
    silently returned empty/zero rich_metrics because to_match() produced no
    moves at all for Hold'em sessions."""
    session = make_holdem_session(rounds=1)
    session.submit_action("A", "fold")
    match = session.to_match()

    extension = session.game.metrics_engine
    report = MatchEvaluator(AgentRegistry()).evaluate(match, extension=extension)
    agent_report = report["agents"]["gpt-5"]
    assert agent_report["the"]["fold_rate"] == 1.0
