from __future__ import annotations

import numpy as np

from outplaylabs_arena.game_components.game_metrics import GameMetrics
from outplaylabs_arena.metrics.extension import GameMetricsExtension


class UltimatumMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        if n == 0:
            return {"total_payoff": dict(total_scores)}

        offers = [e["offer_fraction"] for e in history]
        accepted = [e["accepted"] for e in history]

        return {
            "total_payoff":          dict(total_scores),
            "average_payoff":        {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "avg_offer_fraction":    float(np.mean(offers)) if offers else 0.0,
            "acceptance_rate":       sum(accepted) / n if n else 0.0,
            "offer_fairness_index":  float(np.mean([abs(o - 0.5) for o in offers])) if offers else 0.0,
        }

    def compute_joint(self, match, config: dict) -> dict:
        total_pot = config.get("total", 100.0)

        offers: list[float] = []
        responses: list[str] = []
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            for m in moves:
                action = m.action
                if isinstance(action, (int, float)):
                    offers.append(float(action) / total_pot if total_pot > 0 else 0.0)
                elif isinstance(action, str) and action in ("accept", "reject"):
                    responses.append(action)

        n_resp = len(responses)
        acceptance_rate = responses.count("accept") / n_resp if n_resp else 0.0
        avg_offer = float(np.mean(offers)) if offers else 0.0

        return {
            "ug_avg_offer_fraction":    avg_offer,
            "ug_acceptance_rate":       acceptance_rate,
            "ug_offer_fairness_index":  float(np.mean([abs(o - 0.5) for o in offers])) if offers else 0.0,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        total_pot = config.get("total", 100.0)
        min_fraction = config.get("min_offer", 1.0) / total_pot if total_pot > 0 else 0.01

        actions = match.actions(agent_id)
        offers_made: list[float] = []
        responses_made: list[str] = []

        for i, action in enumerate(actions):
            if isinstance(action, (int, float)):
                offers_made.append(float(action) / total_pot if total_pot > 0 else 0.0)
            elif isinstance(action, str) and action in ("accept", "reject"):
                responses_made.append(action)

        n_offers = len(offers_made)
        n_resp = len(responses_made)

        # Rejection threshold: minimum offer fraction this agent accepts
        # We estimate from history: find minimum accepted offer fraction
        history_data = []
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            for m in moves:
                if m.agent_id == agent_id and isinstance(m.action, str) and m.action in ("accept", "reject"):
                    history_data.append(m)

        # Backward induction: SPE responder accepts any positive offer
        spe_adherence_responder = (
            responses_made.count("accept") / n_resp if n_resp else 0.0
        )
        # SPE proposer offers minimum; deviation = how much above minimum
        spe_adherence_proposer = (
            sum(1 for o in offers_made if o <= min_fraction + 0.05) / n_offers
            if n_offers else 0.0
        )

        return {
            "ug": {
                "avg_offer_fraction":       float(np.mean(offers_made)) if offers_made else 0.0,
                "avg_acceptance_rate":      responses_made.count("accept") / n_resp if n_resp else 0.0,
                "offer_fairness_index":     float(np.mean([abs(o - 0.5) for o in offers_made])) if offers_made else 0.0,
                "backward_induction_proposer": spe_adherence_proposer,
                "backward_induction_responder": spe_adherence_responder,
            }
        }
