from copy import deepcopy
from dataclasses import dataclass

from nash_arena.game_engine import GameEngine
from .metrics import BlottoMetrics

from .agent import Agent


@dataclass
class BlottoState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_actions: dict[str, list[int]]
    history: list[dict]
    total_scores: dict[str, float]


# ** GAME DEFINITION **
#
# Parameters: 2 agents, 5 battlefields, 100 total troops, 10 rounds
#
# Agent submits a list like: [20,10,30,25,15]
# Each number is how many troops it puts on each battlefield
#
# Scoring: higher allocation wins that battlefield, 
#          tie gives both 0.5 pts, 
#          winner of round is whoever wins more battlefield points!
class BlottoGame(GameEngine):
    def __init__(self, num_battlefields=5, total_resources=100, num_rounds=10):
        if num_battlefields < 1:
            raise ValueError("num_battlefields must be at least 1")
        if total_resources < num_battlefields:
            raise ValueError("total_resources must be at least num_battlefields")
        if num_rounds < 1:
            raise ValueError("num_rounds must be at least 1")

        self.num_battlefields = num_battlefields
        self.total_resources = total_resources
        self.num_rounds = num_rounds
        
        self.metrics_engine = BlottoMetrics()

    @classmethod
    def from_config(cls, config):
        return cls(
            num_battlefields=len(config.battlefields),
            total_resources=config.budget[0],
            num_rounds=config.rounds,
        )
        
    def initial_state(self):
        return BlottoState(
            round_number=1,
            phase="awaiting_action",
            awaiting=["A", "B"],
            pending_actions={},
            history=[],
            total_scores={"A": 0, "B": 0},
        )

    # Asks: Is this a valid Blotto allocation?      
    def validate_action(self, action):
        if not isinstance(action, list):
            return False

        if len(action) != self.num_battlefields:
            return False
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in action):
            return False
        if not all(x >= 0 for x in action):
            return False
        if sum(action) != self.total_resources:
            return False

        return True
    
    # Asks: Can this player submit this allocation right now in this state?
    def validate_player_action(self, state, player, action):
        if self.is_terminal(state):
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player}")
        if player not in state.awaiting:
            raise ValueError(f"action already submitted for player {player}")
        if not self.validate_action(action):
            raise ValueError(f"invalid action for player {player}: {action}")

        return True
        
    # Finite State Machine (FSM) - system that can only be in one immutable state at a given time
    def apply_action(self, state, player, action):
        self.validate_player_action(state, player, action)
        next_state = deepcopy(state)

        next_state.pending_actions[player] = action
        next_state.awaiting.remove(player)

        if not next_state.awaiting:
            next_state = self._resolve_state_round(next_state)

        return next_state

    def _resolve_state_round(self, state):
        result = self.play_round(
            state.pending_actions["A"],
            state.pending_actions["B"],
        )

        state.total_scores["A"] += result["score_a"]
        state.total_scores["B"] += result["score_b"]

        state.history.append({
            "round": state.round_number,
            "allocations": {
                "A": result["action_a"],
                "B": result["action_b"],
            },
            "scores": {
                "A": result["score_a"],
                "B": result["score_b"],
            },
            "winner": result["winner"],
            "total_scores": dict(state.total_scores),
        })

        if state.round_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
            state.pending_actions = {}
        else:
            state.round_number += 1
            state.awaiting = ["A", "B"]
            state.pending_actions = {}

        return state

    def is_terminal(self, state):
        return state.phase == "complete"

    def compute_results(self, state, session_id=None, config_hash=None):
        if not self.is_terminal(state):
            raise ValueError("results are only available after game is complete")

        if state.total_scores["A"] > state.total_scores["B"]:
            winner = "A"
        elif state.total_scores["B"] > state.total_scores["A"]:
            winner = "B"
        else:
            winner = "Tie"

        results = {
            "total_scores": dict(state.total_scores),
            "winner": winner,
            "history": list(state.history),
            "metrics": self.metrics_engine.compute(
                history=state.history,
                total_scores=state.total_scores
            )
        }
        
        if session_id is not None:
            results["session_id"] = session_id
        if config_hash is not None:
            results["config_hash"] = config_hash

        return results

    def public_state(self, state, config, session_id, config_hash):
        return {
            "session_id": session_id,
            "config_hash": config_hash,
            "round": state.round_number,
            "round_total": config.rounds,
            "phase": state.phase,
            "awaiting": list(state.awaiting),
            "battlefields": [
                {"id": b.id, "value": b.value}
                for b in config.battlefields
            ],
            "budgets": {"A": config.budget[0], "B": config.budget[1]},
            "total_scores": dict(state.total_scores),
            "history": list(state.history),
        }
        
    def play_round(self, action_a, action_b):
        if not self.validate_action(action_a):
            raise ValueError(f"Invalid action for Agent A: {action_a}")
        if not self.validate_action(action_b):
            raise ValueError(f"Invalid action for Agent B: {action_b}")
        
        score_a = 0
        score_b = 0
        
        for a,b in zip(action_a, action_b):
            if a > b:
                score_a += 1
            elif b > a:
                score_b += 1
            else:
                score_a += .5
                score_b += .5
                
        if score_a > score_b: winner = "A"
        elif score_b > score_a: winner = "B"
        else: winner = "Tie"
        
        return {
            "action_a": action_a,
            "action_b": action_b,
            "score_a": score_a,
            "score_b": score_b,
            "winner": winner
        }
        
    def play_match(self, agent_a: Agent, agent_b: Agent, num_rounds=10):
        history_a = []
        history_b = []
        full_history = []
        
        total_score_a = 0
        total_score_b = 0
        
        for round_idx in range(num_rounds):
            action_a = agent_a.act(history_a)
            action_b = agent_b.act(history_b)
            
            result = self.play_round(action_a, action_b)
            
            total_score_a += result["score_a"]
            total_score_b += result["score_b"]
            
            full_history.append({
                "round": round_idx + 1,
                "agent_a": agent_a.name,
                "agent_b": agent_b.name,
                **result
            })
            
            history_a.append({
                "own_action": action_a,
                "opponent_action": action_b,
                "own_score": result["score_a"],
                "opponent_score": result["score_b"],
                "winner": result["winner"]
            })
            
            history_b.append({
                "own_action": action_b,
                "opponent_action": action_a,
                "own_score": result["score_b"],
                "opponent_score": result["score_a"],
                "winner": result["winner"]
            })
        
        if total_score_a > total_score_b: match_winner = agent_a.name
        elif total_score_b > total_score_a: match_winner = agent_b.name
        else: match_winner = "Tie"
            
        return {
            "agent_a": agent_a.name,
            "agent_b": agent_b.name,
            "total_score_a": total_score_a,
            "total_score_b": total_score_b,
            "match_winner": match_winner,
            "history": full_history
        }
