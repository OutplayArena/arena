# Stag Hunt

A 2-player symmetric coordination game with two Nash equilibria. (Stag, Stag) is Pareto-optimal but risky — it requires mutual trust. (Hare, Hare) is risk-dominant and safe but yields less. Tests whether agents converge on socially optimal vs. safe equilibria and whether they can coordinate via repeated interaction.


## Overview

**Type**: coordination, simultaneous, binary_choice

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `stag_hunt` |  |
| `variant` | `string` | `classic` | Game variant |
| `players` | `integer` | `2` |  |
| `rounds` | `integer` | `10` |  |
| `payoff_stag_stag` | `number` | `4.0` | Payoff when both hunt stag (Pareto-optimal) |
| `payoff_hare_hare` | `number` | `2.0` | Payoff when both hunt hare (risk-dominant) |
| `payoff_stag_hare` | `number` | `0.0` | Payoff for hunting stag alone (sucker payoff) |
| `noise` | `number` | `0.0` | Probability that an action is flipped (noisy variant) |
| `seed` | `['integer', 'null']` | —` |  |
| `system_prompt` | `string` | `` | Optional system prompt override for LLM agents. |

## Metrics

- `total_payoff`
- `average_payoff`
- `stag_rate`
- `mutual_stag_rate`
- `mutual_hare_rate`
- `outcome_counts`
- `sh_outcome_counts`
- `sh_mutual_stag_rate`
- `sh_mutual_hare_rate`
- `sh_price_of_risk`
- `equilibrium_selection_rate`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `nash_gap`
- `cooperation_rate`
- `tit_for_tat_adherence`
- `forgiveness_index`
- `conditional_cooperation`
- `multilateral_cooperation_index`
- `social_welfare`
- `pareto_efficiency`
- `gini_coefficient`

## Built-in Agents

| Agent | Name | Description |
|-------|------|-------------|
| `always_stag` | Always Stag | Always hunts stag. Maximizes joint welfare if opponent cooperates. |
| `always_hare` | Always Hare | Always hunts hare. Safe risk-dominant strategy. |
| `nash_equilibrium` | Nash Equilibrium (Hare) | Plays the risk-dominant Nash equilibrium. |
| `pareto_optimal` | Pareto Optimal (Stag) | Always attempts the Pareto-optimal equilibrium. |
| `tit_for_tat` | Tit for Tat | Starts with stag, then mirrors opponent's last move. |
| `optimistic` | Optimistic (Grim Trigger) | Hunts stag until betrayed once, then always hare. |
| `random` | Random | Chooses uniformly at random each round. |
| `interactive` | Interactive (Human) | You play directly via the Live View panel. |

## Example

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="stag_hunt",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'stag_hunt', 'variant': 'classic', 'players': 2, 'rounds': 10, 'payoff_stag_stag': 4.0, 'payoff_hare_hare': 2.0, 'payoff_stag_hare': 0.0, 'noise': 0.0, 'seed': 42, 'system_prompt': ''},
)
```
