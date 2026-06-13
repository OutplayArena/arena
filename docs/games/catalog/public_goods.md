# Public Goods Game

N players (3–6) simultaneously choose how much to contribute to a shared pool. The pool is multiplied by a factor r and split equally among all players. When r < N, free-riding dominates at Nash equilibrium, but full contribution maximizes social welfare. Supports an optional punishment variant where players can pay to sanction low contributors after each round.


## Overview

**Type**: social_dilemma, simultaneous, continuous

**Players**: 3–6

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `public_goods` |  |
| `variant` | `string` | `classic` | classic = standard PGG; punishment = players can sanction after contributing |
| `players` | `integer` | `4` |  |
| `rounds` | `integer` | `10` |  |
| `endowment` | `number` | `10.0` | Each player's endowment per round |
| `multiplier` | `number` | `2.0` | Pool multiplier r (typically 1.5–3.0; free-riding dominant when r < players) |
| `punishment_cost` | `number` | `1.0` | Cost to punish one unit from another player (punishment variant) |
| `punishment_effect` | `number` | `3.0` | Payoff reduction applied to the target per punishment unit |
| `seed` | `['integer', 'null']` | —` |  |
| `system_prompt` | `string` | `` | Optional system prompt override for LLM agents. |

## Metrics

- `total_payoff`
- `average_payoff`
- `avg_contribution`
- `contribution_rate`
- `avg_pool`
- `free_rider_count`
- `pgg_avg_pool`
- `pgg_contribution_efficiency`
- `pgg_price_of_anarchy`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `social_welfare`
- `pareto_efficiency`
- `gini_coefficient`
- `multilateral_cooperation_index`

## Built-in Agents

| Agent | Description |
|-------|-------------|
| `always_max` | Contributes full endowment every round. |
| `always_zero` | Contributes nothing (Nash equilibrium when r < n). |
| `nash_equilibrium` | Plays zero contribution (dominant strategy). |
| `linear_decay` | Starts at full contribution and decays to zero. |
| `conditional_cooperator` | Matches the average contribution of others. |
| `random` | Contributes a uniformly random amount each round. |

## Example

```python
from nash_arena_sdk import quick_play

results = quick_play(
    game="public_goods",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'public_goods', 'variant': 'classic', 'players': 4, 'rounds': 10, 'endowment': 10.0, 'multiplier': 2.0, 'punishment_cost': 1.0, 'punishment_effect': 3.0, 'seed': 42, 'system_prompt': ''},
)
```
