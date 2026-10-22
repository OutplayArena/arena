"""Conservative match/history integration for deterministic symmetric two-player matrix games."""

import math
from abc import abstractmethod

from arena.metrics.contracts import Match, Move
from arena.metrics.extension import GameMetricsExtension
from arena.metrics.external_regret import FiniteActionGame, external_regret, unavailable


def matrix_history_match(
    history: list[dict],
    game_type: str,
    config: dict,
    *,
    match_id: str = "history",
    agent_names: dict[str, str] | None = None,
    completed: bool = True,
) -> Match:
    """Preserve missing fields, forfeits, and noise evidence when loading history.

    Missing payoffs receive a placeholder only for legacy consumers; metadata
    prevents the exact metric from treating that placeholder as an observation.
    """
    names = agent_names if agent_names is not None else {"A": "A", "B": "B"}
    moves = []
    for entry in history:
        if not isinstance(entry, dict):
            entry = {}
        actions = entry.get("actions") or {}
        scores = entry.get("payoffs") or entry.get("scores") or {}
        if not isinstance(actions, dict):
            actions = {}
        if not isinstance(scores, dict):
            scores = {}
        for role, agent in names.items():
            payoff = scores.get(role)
            invalid_payoff = (
                isinstance(payoff, bool)
                or not isinstance(payoff, (int, float))
                or not math.isfinite(payoff)
            )
            round_number = entry.get("round")
            invalid_round = type(round_number) is not int or round_number < 0
            action = actions.get(role)
            moves.append(
                Move(
                    agent_id=agent,
                    round_number=0 if invalid_round else round_number,
                    action=action if isinstance(action, str) else None,
                    payoff=0.0 if invalid_payoff else payoff,
                    metadata={
                        "forfeit": bool(
                            entry.get("forfeit") or entry.get("forfeit_by")
                        ),
                        "action_noise": "intended_actions" in entry,
                        "missing_payoff": role not in scores,
                        "invalid_payoff": invalid_payoff,
                        "invalid_round": invalid_round,
                    },
                )
            )
    return Match(
        match_id=match_id,
        game_type=game_type,
        agent_ids=list(names.values()),
        moves=moves,
        config=config,
        metadata={"completed": completed},
    )


class MatrixRegretExtension(GameMetricsExtension):
    """Exact-regret integration for symmetric two-player games with identical action sets."""

    def __init__(self, config: dict | None = None) -> None:
        self.regret_config = config or {}

    @abstractmethod
    def regret_game(self, config: dict) -> FiniteActionGame:
        """Build the deterministic adapter using this game's configured engine."""
        ...

    def compute_external_regret(
        self, match: Match, agent_id: str, config: dict
    ) -> dict:
        """Reject ambiguous trajectories instead of evaluating a selected subset."""
        config = {**self.regret_config, **config}
        if len(match.agent_ids) != 2 or len(set(match.agent_ids)) != 2:
            return unavailable("requires two distinct player identities")
        if agent_id not in match.agent_ids:
            return unavailable("unknown player identity")
        if match.metadata.get("completed") is False:
            return unavailable("match is incomplete")
        if config.get("noise", 0) != 0 or any(
            m.metadata.get("action_noise") or "intended_actions" in m.metadata
            for m in match.moves
        ):
            return unavailable("action noise prevents exact decision counterfactuals")
        if any(
            m.metadata.get("forfeit") or m.metadata.get("forfeit_by")
            for m in match.moves
        ):
            return unavailable(
                "forfeited rounds have no observed strategic counterfactual"
            )
        if any(m.metadata.get("missing_payoff") for m in match.moves):
            return unavailable("missing logged payoff")
        if any(m.metadata.get("invalid_payoff") for m in match.moves):
            return unavailable("invalid logged payoff")
        if any(m.metadata.get("invalid_round") for m in match.moves):
            return unavailable("invalid round number")
        rounds: dict[int, dict[str, Move]] = {}
        for move in match.moves:
            r = move.round_number
            if type(r) is not int or r < 0:
                return unavailable("invalid round number")
            row = rounds.setdefault(r, {})
            if move.agent_id not in match.agent_ids or move.agent_id in row:
                return unavailable("unknown or duplicate player move")
            row[move.agent_id] = move
        ordered = sorted(rounds)
        n = len(ordered)
        if ordered and ordered not in (list(range(n)), list(range(1, n + 1))):
            return unavailable("rounds must be contiguous and start at zero or one")
        if any(set(row) != set(match.agent_ids) for row in rounds.values()):
            return unavailable("incomplete round: both players must be observed")
        if "rounds" in config and config["rounds"] != n:
            return unavailable("trajectory length disagrees with configured rounds")
        opponent = next(a for a in match.agent_ids if a != agent_id)
        own = [rounds[r][agent_id] for r in ordered]
        other = [rounds[r][opponent] for r in ordered]
        try:
            game = self.regret_game(config)
            external_regret(
                game,
                [m.action for m in other],
                [m.action for m in own],
                [m.payoff for m in other],
            )
            return external_regret(
                game,
                [m.action for m in own],
                [m.action for m in other],
                [m.payoff for m in own],
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            return unavailable(f"invalid trajectory or configuration: {exc}")

    def history_external_regret(self, history: list[dict], game_type: str) -> dict:
        """Compute the same metric for the legacy engine result, keyed by role."""
        match = matrix_history_match(history, game_type, self.regret_config)
        return {
            a: self.compute_external_regret(match, a, self.regret_config)
            for a in match.agent_ids
        }
