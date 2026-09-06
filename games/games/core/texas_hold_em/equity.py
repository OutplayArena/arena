"""Post-hoc hand-equity calculator for Texas Hold'em (issue #24).

Computes each player's win probability given known hole cards and the
community cards revealed so far. This is intentionally post-hoc (run after a
hand's hole cards are already known from `state.history`, not fed live to an
acting agent) and reuses the existing hand evaluator in `engine.py` rather
than adding a new poker-equity dependency:

- Flop/turn (2 or 1 unknown board cards): exact enumeration over every
  possible completion (990 / 45 combinations) -- cheap and exact.
- Preflop (5 unknown board cards, C(48, 5) ~= 1.7M combinations): exact
  enumeration is too expensive to run post-hoc for every hand, so this
  samples random completions (Monte Carlo) instead. The result is an
  approximation; increase `mc_trials` for tighter estimates at higher cost.

Not wired into the automatic per-game metrics pipeline: computing this for
every hand of every game would add a real cost to `compute_results` for
long-running benchmark tournaments (hundreds-to-thousands of rounds is a
normal use case on this platform). Callers who want it (e.g. a richer History
view) can call `hand_equity`/`preflop_equity_for_hand` explicitly.
"""
from __future__ import annotations

import random
from itertools import combinations

from games.core.texas_hold_em.engine import DECK, _best_hand


def hand_equity(
    hole_cards: dict[str, list[str]],
    community: list[str],
    live_players: list[str],
    mc_trials: int = 500,
    seed: int | None = None,
) -> dict[str, float]:
    """
    Win probability for each of `live_players`, given their known hole cards
    and the community cards revealed so far. Ties split their share equally
    among the tied winners for that board completion.

    Returns an empty dict if `live_players` is empty, or {player: 1.0} if
    only one player is live (no contest possible).
    """
    if not live_players:
        return {}
    if len(live_players) == 1:
        return {live_players[0]: 1.0}

    known = set(community)
    for p in live_players:
        known.update(hole_cards.get(p, []))
    remaining = [c for c in DECK if c not in known]
    needed = 5 - len(community)

    wins = {p: 0.0 for p in live_players}
    trials = 0

    def _score_board(board: tuple[str, ...]) -> None:
        nonlocal trials
        full_board = community + list(board)
        scores = {
            p: _best_hand(hole_cards.get(p, []), full_board)[:2]
            for p in live_players
        }
        best = max(scores.values())
        winners = [p for p, s in scores.items() if s == best]
        share = 1.0 / len(winners)
        for w in winners:
            wins[w] += share
        trials += 1

    if needed <= 0:
        _score_board(())
    elif needed <= 2:
        # Exact enumeration: turn->river (45 combos) or flop->river (990).
        for board in combinations(remaining, needed):
            _score_board(board)
    else:
        # Preflop: C(48, 5) ~= 1.7M combinations is too slow to enumerate
        # post-hoc for every hand -- sample instead.
        rng = random.Random(seed)
        for _ in range(mc_trials):
            board = tuple(rng.sample(remaining, needed))
            _score_board(board)

    if trials == 0:
        return {p: 0.0 for p in live_players}
    return {p: wins[p] / trials for p in live_players}


def preflop_equity_for_hand(
    hole_cards: dict[str, list[str]],
    player_ids: list[str],
    mc_trials: int = 500,
    seed: int | None = None,
) -> dict[str, float]:
    """Convenience wrapper: preflop (no community cards) equity for every
    player originally dealt into a hand, regardless of who later folded."""
    return hand_equity(hole_cards, [], list(player_ids), mc_trials=mc_trials, seed=seed)
