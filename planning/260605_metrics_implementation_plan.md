# Agent Evaluation Platform — Implementation Plan
### Game-Theoretic Metrics for Cooperative & Competitive Agent Analysis

---

## Overview

This plan translates the literature review and metrics engine into a concrete, phased implementation for a Python backend platform where agents connect via MCP and submit decisions (e.g., Colonel Blotto allocations). The platform already has: MCP connectivity, a frontend, a backend with modular design, and full move history persistence.

**Goal:** A full-stack metrics pipeline that computes Tier 1–3 metrics after every match, maintains cross-match state for α-Rank, and exposes results via an analytics API.

---

## Phase 1 — Data Layer: Translate Move History to Metrics Contracts

**What:** Wrap your existing persistence model with the `Move` and `Match` data contracts from `metrics_engine_v2.py`.

**Why:** The metrics engine needs a consistent shape regardless of game type. This translation layer isolates your storage schema from the metrics logic.

### Step 1.1 — Define the translation function

```python
# adapters.py
from metrics_engine_v2 import Move, Match

def match_from_db(match_record: dict, move_records: list[dict]) -> Match:
    """
    Translate your existing DB records into the metrics engine's
    Match contract. Adapt field names to match your schema.
    """
    moves = [
        Move(
            agent_id=m["agent_id"],
            round_number=m["round"],
            action=m["allocation"],      # list[int] for Blotto, int for PD
            payoff=m["payoff"],
            metadata=m.get("metadata", {}),
        )
        for m in move_records
    ]
    return Match(
        match_id=match_record["id"],
        game_type=match_record["game_type"],   # "colonel_blotto", "prisoners_dilemma", etc.
        agent_ids=match_record["agent_ids"],
        moves=moves,
        config=match_record.get("config", {}),
    )
```

### Step 1.2 — Extend your config schema

Add these fields to the game config your platform already stores. They are optional but unlock more precise metrics:

```python
# Example config for a Colonel Blotto match
game_config = {
    "game_type":                  "colonel_blotto",
    "resources":                  100,
    "battlefields":               5,
    "rounds":                     20,
    "tie_policy":                 "split",         # "split" | "no_win"
    "pareto_optimal_welfare":     5.0,             # max possible fronts × rounds
    "total_resources_all_agents": 400,             # resources × num_agents
    "best_responses": {                            # optional; use observed max if absent
        "agent_alpha": 3.5,
        "agent_beta":  3.2,
    },
}

# Example config for Prisoner's Dilemma
pd_config = {
    "game_type":              "prisoners_dilemma",
    "rounds":                 20,
    "pareto_optimal_welfare": 6.0,  # CC_payoff × 2 × rounds / rounds = CC_payoff × 2
}
```

### Step 1.3 — Verify the translation

```python
# Quick smoke test — run against a real match from your DB
match_record = db.get_match("match_001")
move_records  = db.get_moves("match_001")

match = match_from_db(match_record, move_records)

print(f"Agents:     {match.agent_ids}")
print(f"Rounds:     {match.num_rounds()}")
print(f"Moves:      {len(match.moves)}")
print(f"Payoffs[0]: {match.payoffs(match.agent_ids[0])[:5]}")

# Expected: no errors, sensible values
```

---

## Phase 2 — Core Metrics Pipeline: Per-Match Evaluation

**What:** After every match completes, call `MatchEvaluator.evaluate()` and store the report.

**Why:** This is the main computation loop. Everything downstream (rankings, dashboards, research exports) reads from these stored reports.

### Step 2.1 — Initialise the evaluator (singleton, persisted across matches)

```python
# metrics_service.py
from metrics_engine_v2 import AgentRegistry, MatchEvaluator

# The registry is the only stateful object — it accumulates payoff
# data across matches for α-Rank. It must persist for the lifetime
# of a tournament session. Store it in your app's service layer.
registry  = AgentRegistry(alpha=50.0)   # alpha: selection intensity for α-Rank
evaluator = MatchEvaluator(registry)
```

### Step 2.2 — Hook into your match completion event

```python
# In your existing match handler (FastAPI / Django / Flask / custom)

from adapters import match_from_db
from metrics_service import evaluator

def on_match_complete(match_id: str) -> None:
    """
    Call this immediately after a match finishes and payoffs are settled.
    """
    # 1. Load from your existing persistence
    match_record = db.get_match(match_id)
    move_records  = db.get_moves(match_id)

    # 2. Translate to metrics contract
    match = match_from_db(match_record, move_records)

    # 3. Compute all metrics
    report = evaluator.evaluate(match)

    # 4. Persist the report alongside the match
    db.save_metrics(match_id=match_id, metrics=report)

    # 5. (Optional) Emit to analytics queue / websocket for live dashboard
    analytics_queue.publish("match_metrics", report)
```

### Step 2.3 — Understand the report structure

```python
# report shape after evaluate()
{
    "match_id":   "match_001",
    "game_type":  "colonel_blotto",
    "num_agents": 4,

    # ── Joint metrics (whole match) ──────────────────────────────────
    "joint": {
        "social_welfare":          12.4,
        "pareto_efficiency":       0.82,
        "social_efficiency_ratio": 0.82,
        "gini_coefficient":        0.09,    # 0=equal, 1=one agent takes all
        "nash_gap_per_agent": {
            "agent_alpha": 0.6,
            "agent_beta":  1.1,
            "agent_gamma": 0.3,
            "agent_delta": 0.8,
        },
        "total_nash_gap": 2.8,

        # Blotto-specific joint metrics
        "blotto_fronts_won": {
            "agent_alpha": 0.31,
            "agent_beta":  0.27,
            "agent_gamma": 0.22,
            "agent_delta": 0.20,
        },
        "blotto_targeting_overlap": {
            "agent_alpha_agent_beta": 0.86,   # high = fighting same fronts
            "agent_alpha_agent_gamma": 0.74,
            # ... all pairs
        },
    },

    # ── Per-agent metrics ────────────────────────────────────────────
    "agents": {
        "agent_alpha": {
            "total_payoff":           18.6,
            "avg_payoff":             1.86,
            "strategy_entropy":       3.21,   # higher = more mixed / unpredictable
            "behavioral_consistency": 0.54,   # higher = more deterministic
            "cumulative_regret":      4.2,    # lower = closer to best-response
            "adaptive_regret_series": [2.1, 1.8, 0.9, 0.4],  # improving over time?
            "nash_gap":               0.6,

            # Blotto-specific
            "blotto": {
                "avg_hhi":                0.28,   # 0=spread, 1=all-in-one
                "strategy_diversity":     3.21,
                "pattern_exploitability": 0.19,   # 0=random, 1=predictable
                "underdog_performance":   1.08,   # >1 = outperforms resource share
            },
        },
        # ... other agents
    },

    # ── Pairwise signals (cooperative games only) ────────────────────
    "pairwise": {
        "reciprocity_matrix": {
            "agent_alpha_agent_beta": 0.61,
            "agent_beta_agent_alpha": 0.44,
            # ... all directed pairs
        },
    },
}
```

---

## Phase 3 — Cross-Match State: α-Rank and Population Rankings

**What:** After a batch of matches (tournament round or session end), compute α-Rank scores and Elo ratings across the full agent population.

**Why:** Individual match metrics tell you how an agent performed in one game. α-Rank tells you which strategies are evolutionarily dominant across the whole ecosystem — it is the primary population-level ranking.

### Step 3.1 — Run after a tournament batch

```python
# After N matches complete (e.g., end of a round-robin)

def compute_population_rankings(agent_ids: list[str]) -> dict:
    """
    Returns Elo + α-Rank scores for all agents.
    Call after a batch of matches, not after every single match.
    """
    from metrics_service import evaluator
    return evaluator.population_report(agent_ids)

# Example output:
# {
#     "elo_ratings": {
#         "agent_alpha": 1247.3,
#         "agent_beta":  1189.1,
#         "agent_gamma": 1204.6,
#         "agent_delta": 1158.9,
#     },
#     "alpha_rank_scores": {
#         "agent_alpha": 0.41,    # dominant strategy
#         "agent_beta":  0.28,
#         "agent_gamma": 0.19,
#         "agent_delta": 0.12,
#     },
#     "alpha_rank_ranking": ["agent_alpha", "agent_beta", "agent_gamma", "agent_delta"],
#     "population_diversity": 1.83,   # Shannon entropy — higher = more diverse ecosystem
#     "matches_played": 42,
# }
```

### Step 3.2 — Why α-Rank instead of just Elo

```python
# Elo fails silently on intransitive strategies.
# Example: Rock-Paper-Scissors tournament

# Elo result (wrong — picks a spurious winner):
# rock:     1216  ← "wins" by random draw
# random:   1215
# scissors: 1185
# paper:    1183

# α-Rank result (correct — reflects the cycle):
# paper:    0.40  ← highest mass because it beats rock, which is common
# scissors: 0.30
# rock:     0.20
# random:   0.10

# In Colonel Blotto, the same intransitivity is common:
# Strategy A beats B, B beats C, C beats A.
# Always report BOTH, but use α-Rank as the authoritative ranking.
```

### Step 3.3 — Tune the alpha parameter

```python
# AgentRegistry(alpha=X) controls selection intensity for α-Rank.
# Alpha affects how sharply the ranking differentiates strategies.

# Low alpha  (e.g., 10):  near-uniform distribution — strategies look equally dominant
# Mid alpha  (e.g., 50):  balanced — good default for most games
# High alpha (e.g., 100): near-deterministic — winner-takes-all ranking

# Recommended: start at alpha=50, then run a sensitivity check:
for alpha in [10, 25, 50, 100, 200]:
    reg = AgentRegistry(alpha=alpha)
    # ... replay match history into reg ...
    scores = reg.compute_alpha_rank_scores(agent_ids)
    print(f"alpha={alpha}: {scores}")
# If ranking order is stable across alpha values, you have a robust result.
```

---

## Phase 4 — Cooperative & Behavioral Analysis

**What:** Extract the richer behavioral signals that distinguish your platform from a simple leaderboard.

**Why:** This is the research value — understanding *how* agents behave, not just *whether* they win.

### Step 4.1 — Cooperation analysis (repeated games)

```python
# For games with cooperation structure (PD, public goods, blotto_coalition)
# the report["agents"][agent_id] will contain:

def summarise_cooperation(report: dict, agent_id: str) -> None:
    ag = report["agents"][agent_id]

    print(f"=== {agent_id} ===")
    print(f"Cooperation rate: {ag['cooperation_rate']:.1%}")

    # Per-opponent conditional cooperation
    for opp_id, cc in ag["conditional_cooperation"].items():
        print(f"  vs {opp_id}:")
        print(f"    After opponent cooperates: {cc['after_cooperate']:.1%}")
        print(f"    After opponent defects:    {cc['after_defect']:.1%}")

    # TfT adherence per opponent
    print(f"Mean TfT adherence: {ag['mean_tft_adherence']:.1%}")
    for opp_id, tft in ag["tit_for_tat_adherence"].items():
        print(f"  vs {opp_id}: {tft:.1%}")

    # Forgiveness
    print(f"Mean forgiveness index: {ag['mean_forgiveness']:.1f} rounds")
```

### Step 4.2 — Multilateral cooperation dynamics

```python
# Track cooperation collapse or emergence over time
import matplotlib.pyplot as plt

def plot_cooperation_dynamics(report: dict) -> None:
    coop_index = report["joint"].get("multilateral_cooperation_index", [])
    if not coop_index:
        return

    plt.figure(figsize=(10, 4))
    plt.plot(coop_index, marker="o", linewidth=2)
    plt.axhline(y=0.5, linestyle="--", color="gray", label="50% cooperation")
    plt.ylim(0, 1)
    plt.xlabel("Round")
    plt.ylabel("Fraction cooperating")
    plt.title(f"Multilateral Cooperation Index — {report['match_id']}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"coop_{report['match_id']}.png")
```

### Step 4.3 — Reciprocity matrix (who responds to whom)

```python
# report["pairwise"]["reciprocity_matrix"] gives lag-1 correlation
# between every agent pair. Positive = responsive (reciprocates).
# Negative = contrarian. Near-zero = ignores opponent.

def print_reciprocity_matrix(report: dict, agent_ids: list[str]) -> None:
    matrix = report["pairwise"].get("reciprocity_matrix", {})
    print(f"{'':15s}", end="")
    for b in agent_ids:
        print(f"{b:12s}", end="")
    print()
    for a in agent_ids:
        print(f"{a:15s}", end="")
        for b in agent_ids:
            if a == b:
                print(f"{'---':12s}", end="")
            else:
                key = f"{a}_{b}"
                val = matrix.get(key, 0.0)
                print(f"{val:+.3f}      ", end="")
        print()
```

---

## Phase 5 — Blotto-Specific Analysis

**What:** Domain metrics unique to Colonel Blotto that reveal strategy quality.

### Step 5.1 — Strategy concentration and diversity

```python
def blotto_strategy_profile(report: dict, agent_id: str) -> dict:
    """
    Returns a summary of an agent's Blotto strategy quality.
    """
    b = report["agents"][agent_id]["blotto"]
    return {
        # HHI: Herfindahl-Hirschman Index
        # 0.2 = perfectly spread (1/5 per battlefield for 5 fronts)
        # 1.0 = all-in on one battlefield
        "concentration":       b["avg_hhi"],
        "concentration_label": "focused" if b["avg_hhi"] > 0.4 else
                                "balanced" if b["avg_hhi"] > 0.25 else "spread",

        # Strategy diversity: entropy of allocation distribution
        # Higher = more mixed strategy (closer to Nash-optimal for Blotto)
        "diversity":           b["strategy_diversity"],

        # Pattern exploitability: lag-1 autocorrelation
        # 0 = random (hard to exploit), 1 = perfectly predictable
        "exploitability":      b["pattern_exploitability"],
        "exploitable":         b["pattern_exploitability"] > 0.4,

        # Underdog performance: fronts_won / resource_share
        # > 1.0 = outperforms resource allocation
        "underdog_index":      b["underdog_performance"],
    }
```

### Step 5.2 — Detect implicit coordination via targeting overlap

```python
def detect_coalition_signatures(report: dict, threshold: float = 0.5) -> list[tuple]:
    """
    In N-player Blotto, low targeting overlap between two agents can indicate
    implicit coordination — they're partitioning the battlefield rather than
    competing directly, at the expense of a third agent.

    Returns pairs with overlap BELOW threshold (potential implicit allies).
    """
    overlaps = report["joint"].get("blotto_targeting_overlap", {})
    low_overlap_pairs = [
        (pair, overlap)
        for pair, overlap in overlaps.items()
        if overlap < threshold
    ]
    return sorted(low_overlap_pairs, key=lambda x: x[1])

# Example usage:
# pairs = detect_coalition_signatures(report, threshold=0.5)
# [("agent_alpha_agent_gamma", 0.31), ...]
# → agent_alpha and agent_gamma may be implicitly coordinating
```

### Step 5.3 — Mixed NE distance (small games only)

```python
# For Blotto with 2 battlefields and equal resources, the NE is known analytically.
# For larger games, compute numerically with nashpy or OpenSpiel.

# Example: 2-battlefield NE approximation (uniform over valid splits)
def approximate_blotto_ne_2battlefield(resources: int) -> dict[tuple, float]:
    """
    For 2-battlefield Blotto, the symmetric NE is the uniform distribution
    over all valid (x, resources-x) allocations with x in [0, resources].
    This is an approximation — see Roberson (2006) for exact conditions.
    """
    allocations = [(x, resources - x) for x in range(resources + 1)]
    prob = 1.0 / len(allocations)
    return {a: prob for a in allocations}

# Then:
from metrics_engine_v2 import BlottoMetrics

ne_dist = approximate_blotto_ne_2battlefield(resources=10)
observed_allocs = match.actions("agent_alpha")
kl_distance = BlottoMetrics.mixed_ne_distance(observed_allocs, ne_dist)
print(f"NE distance (KL divergence): {kl_distance:.4f}")
# Lower = agent's mixed strategy is closer to the theoretical Nash equilibrium
```

---

## Phase 6 — API Endpoints

**What:** Expose metrics to your existing frontend.

### Step 6.1 — Match metrics endpoint

```python
# routes/metrics.py  (FastAPI example — adapt to your framework)
from fastapi import APIRouter
from metrics_service import evaluator
from adapters import match_from_db

router = APIRouter(prefix="/metrics")

@router.get("/match/{match_id}")
def get_match_metrics(match_id: str):
    """Returns stored per-match metrics report."""
    return db.get_metrics(match_id)

@router.post("/match/{match_id}/compute")
def compute_match_metrics(match_id: str):
    """(Re)compute metrics for a match. Useful for backfill."""
    match_record = db.get_match(match_id)
    move_records  = db.get_moves(match_id)
    match         = match_from_db(match_record, move_records)
    report        = evaluator.evaluate(match)
    db.save_metrics(match_id, report)
    return report
```

### Step 6.2 — Population rankings endpoint

```python
@router.get("/population/{session_id}")
def get_population_rankings(session_id: str):
    """α-Rank and Elo for all agents in a session/tournament."""
    agent_ids = db.get_session_agents(session_id)
    return evaluator.population_report(agent_ids)
```

### Step 6.3 — Agent profile endpoint

```python
@router.get("/agent/{agent_id}/profile")
def get_agent_profile(agent_id: str, last_n_matches: int = 20):
    """
    Aggregate metrics across recent matches for a single agent.
    Useful for agent identity cards on the frontend.
    """
    match_ids = db.get_recent_matches(agent_id, limit=last_n_matches)
    reports   = [db.get_metrics(mid) for mid in match_ids]

    # Aggregate key signals
    avg_cooperation   = []
    avg_entropy       = []
    avg_regret        = []
    avg_exploitability = []

    for r in reports:
        ag = r["agents"].get(agent_id, {})
        if "cooperation_rate" in ag:
            avg_cooperation.append(ag["cooperation_rate"])
        avg_entropy.append(ag.get("strategy_entropy", 0))
        avg_regret.append(ag.get("cumulative_regret", 0))
        if "blotto" in ag:
            avg_exploitability.append(ag["blotto"]["pattern_exploitability"])

    return {
        "agent_id":                agent_id,
        "matches_analysed":        len(reports),
        "avg_cooperation_rate":    sum(avg_cooperation) / len(avg_cooperation) if avg_cooperation else None,
        "avg_strategy_entropy":    sum(avg_entropy) / len(avg_entropy) if avg_entropy else None,
        "avg_cumulative_regret":   sum(avg_regret) / len(avg_regret) if avg_regret else None,
        "avg_pattern_exploitability": sum(avg_exploitability) / len(avg_exploitability) if avg_exploitability else None,
        "elo_rating":              evaluator.registry.elo_ratings.get(agent_id),
    }
```

---

## Phase 7 — Optional Extensions

### 7.1 — Theory of Mind: opponent prediction tracking

Add an optional field to your MCP submission schema. Agents can submit predictions alongside their decisions; you score accuracy automatically.

```python
# MCP submission schema extension (optional field)
{
    "allocation": [30, 25, 20, 15, 10],          # required
    "predicted_opponent_allocations": {            # optional
        "agent_beta":  [20, 30, 20, 20, 10],
        "agent_gamma": [25, 20, 25, 15, 15],
    }
}

# Scoring in your match handler:
from metrics_engine_v2 import BehavioralMetrics

def score_predictions(match: Match) -> dict[str, dict[str, float]]:
    """
    Returns {agent_id: {opponent_id: prediction_accuracy}}
    """
    results = {}
    for agent_id in match.agent_ids:
        predicted = {}
        actual    = {}
        for move in match.moves_by_agent(agent_id):
            preds = move.metadata.get("predicted_opponent_allocations", {})
            for opp_id, pred_alloc in preds.items():
                predicted.setdefault(opp_id, []).append(pred_alloc)
        for opp_id in match.agent_ids:
            if opp_id != agent_id:
                actual[opp_id] = match.actions(opp_id)
        results[agent_id] = BehavioralMetrics.per_opponent_prediction_accuracy(
            predicted, actual
        )
    return results
```

### 7.2 — Regret trend: is the agent learning?

```python
def is_agent_improving(report: dict, agent_id: str) -> dict:
    """
    Checks whether cumulative regret is declining over the match,
    which indicates the agent is adapting (learning) rather than playing
    a fixed strategy.
    """
    series = report["agents"][agent_id]["adaptive_regret_series"]
    if len(series) < 3:
        return {"improving": None, "trend": None}

    # Simple linear regression slope
    x = list(range(len(series)))
    slope = float(np.polyfit(x, series, 1)[0])
    return {
        "improving": slope < 0,    # negative slope = regret declining
        "trend":     slope,
        "series":    series,
    }
```

### 7.3 — Shapley value hook (multi-player coalition games)

```python
# For coalition games, plug in externally computed Shapley values.
# Shapley computation is game-specific — use the 'shap' library or
# implement analytically for small games.

from metrics_engine_v2 import CooperativeMetrics

# After computing Shapley values externally:
shapley_values = {
    "agent_alpha": 3.2,
    "agent_beta":  2.8,
    "agent_gamma": 2.1,
}
actual_payoffs = {a: report["agents"][a]["avg_payoff"] for a in shapley_values}

deviations = CooperativeMetrics.shapley_value_deviation(actual_payoffs, shapley_values)
# Positive deviation = agent received more than their fair share
# Negative deviation = agent was exploited
print(deviations)
# {"agent_alpha": +0.4, "agent_beta": -0.3, "agent_gamma": -0.1}
```

---

## Summary: What to Build in Order

| Phase | What | Key output |
|-------|------|------------|
| 1 | Data adapter (`match_from_db`) | `Match` objects from your DB |
| 2 | `on_match_complete` hook | Per-match metrics report stored to DB |
| 3 | `population_report` after batches | α-Rank + Elo leaderboard |
| 4 | Cooperation analysis helpers | Per-agent behavioral profiles |
| 5 | Blotto-specific analysis | Concentration, exploitability, coalition signals |
| 6 | API endpoints | Frontend-consumable metrics |
| 7 | Optional: prediction tracking, Shapley | Research-grade behavioral depth |

**Files from this conversation:**
- `metrics_engine_v2.py` — the full metrics engine (multi-agent, all tiers)
- `agent_evaluation_metrics_research.md` — literature review and metric definitions
- `integration_examples.py` — worked examples for Blotto, PD, and tournaments

---

*Generated June 2026 | Based on: Omidshafiei et al. (2019), Camerer et al. (2004), Axelrod (1984), Roberson (2006), Jia et al. (2025)*