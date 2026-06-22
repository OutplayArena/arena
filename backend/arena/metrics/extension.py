from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.metrics.contracts import Match


class GameMetricsExtension(ABC):
    """
    Optional plug-in interface for game-specific metrics.

    Implement this in a game's metrics.py to inject domain metrics into the
    MatchEvaluator report without touching the evaluator itself.

    The evaluator merges the returned dicts into the report:
      compute_joint()   → report["joint"]
      compute_agent()   → report["agents"][agent_id]
      compute_pairwise() → report["pairwise"]   (optional — default returns {})
    """

    @abstractmethod
    def compute_joint(self, match: "Match", config: dict) -> dict:
        """Game-specific keys to merge into report['joint']."""
        ...

    @abstractmethod
    def compute_agent(
        self,
        match: "Match",
        agent_id: str,
        config: dict,
        joint: dict,
    ) -> dict:
        """Game-specific keys to merge into report['agents'][agent_id]."""
        ...

    def compute_pairwise(self, match: "Match", config: dict) -> dict:
        """Game-specific keys to merge into report['pairwise']. Override if needed."""
        return {}
