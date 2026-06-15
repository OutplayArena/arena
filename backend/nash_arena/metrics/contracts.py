from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Move:
    """A single decision submitted by one agent in one round."""
    agent_id: str
    round_number: int
    action: Any           # list[int] for Blotto, int for binary games, etc.
    payoff: float
    metadata: dict = field(default_factory=dict)


@dataclass
class Match:
    """One completed match between 2..N agents."""
    match_id: str
    game_type: str
    agent_ids: list[str]
    moves: list[Move]
    config: dict = field(default_factory=dict)

    def moves_by_agent(self, agent_id: str) -> list[Move]:
        return sorted(
            [m for m in self.moves if m.agent_id == agent_id],
            key=lambda m: m.round_number,
        )

    def moves_by_round(self, r: int) -> list[Move]:
        return [m for m in self.moves if m.round_number == r]

    def num_rounds(self) -> int:
        # +1 so that range(num_rounds()) covers all 1-indexed round numbers
        return max((m.round_number for m in self.moves), default=0) + 1

    def payoffs(self, agent_id: str) -> list[float]:
        return [m.payoff for m in self.moves_by_agent(agent_id)]

    def total_payoff(self, agent_id: str) -> float:
        return sum(self.payoffs(agent_id))

    def actions(self, agent_id: str) -> list[Any]:
        return [m.action for m in self.moves_by_agent(agent_id)]

    def joint_payoffs(self) -> list[tuple[float, ...]]:
        """One payoff tuple per round, in agent_ids order."""
        result = []
        for r in range(self.num_rounds()):
            round_moves = {m.agent_id: m for m in self.moves_by_round(r)}
            if all(a in round_moves for a in self.agent_ids):
                result.append(tuple(round_moves[a].payoff for a in self.agent_ids))
        return result
