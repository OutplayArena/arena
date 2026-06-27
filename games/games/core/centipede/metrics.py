from __future__ import annotations

from arena.game_components.game_metrics import GameMetrics
from arena.metrics.extension import GameMetricsExtension


class CentipedeMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        take_steps = [e["step"] for e in history if e.get("action") == "take"]
        steps_played = len(history)
        ended_by_take = bool(take_steps)

        return {
            "total_payoff":       dict(total_scores),
            "steps_played":       steps_played,
            "game_ended_early":   ended_by_take,
            "take_step":          take_steps[0] if take_steps else None,
        }

    def compute_joint(self, match, config: dict) -> dict:
        max_steps = config.get("max_steps", 6)
        actions = []
        for r in range(match.num_rounds()):
            for m in match.moves_by_round(r):
                if isinstance(m.action, str) and m.action in ("take", "pass"):
                    actions.append((r + 1, m.agent_id, m.action))

        steps_played = len(actions)
        take_at = next((step for step, _, act in actions if act == "take"), None)

        # Backward induction adherence: SPE = always take on first opportunity.
        # 1.0 if the first action in the game was "take", else 0.0.
        bi_adherence = 1.0 if (actions and actions[0][2] == "take") else 0.0

        # Cooperation index: fraction of available pass opportunities used
        pass_count = sum(1 for _, _, a in actions if a == "pass")
        cooperation_index = pass_count / max_steps if max_steps > 0 else 0.0

        return {
            "cp_steps_played":              steps_played,
            "cp_take_at_step":              take_at,
            "cp_backward_induction_adherence": bi_adherence,
            "cp_cooperation_index":         cooperation_index,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        actions = [a for a in match.actions(agent_id) if isinstance(a, str) and a in ("take", "pass")]
        n = len(actions)
        if n == 0:
            return {}

        take_count = actions.count("take")
        # SPE: always take first → backward_induction_adherence = 1 if first action is "take"
        bi_adherence = 1.0 if (actions and actions[0] == "take") else 0.0
        cooperation_rate = actions.count("pass") / n

        return {
            "cp": {
                "take_rate":                   take_count / n,
                "cooperation_rate":            cooperation_rate,
                "backward_induction_adherence": bi_adherence,
                "first_action":                actions[0] if actions else None,
            }
        }
