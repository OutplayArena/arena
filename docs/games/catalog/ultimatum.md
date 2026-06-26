# Ultimatum Game

Player A proposes a split of a fixed sum; Player B accepts or rejects. Both get zero on rejection. Nash prediction: A proposes minimum positive amount, B accepts any positive offer. Humans reject "unfair" offers, revealing fairness norms. Tests strategic generosity, backward induction adherence, and fairness preferences.


## Overview

**Type**: bargaining, perfect, continuous

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `ultimatum` |  |
| `players` | `integer` | `2` |  |
| `rounds` | `integer` | `10` | Number of rounds (roles swap every round) |
| `total` | `number` | `100.0` | Total amount to split each round |
| `min_offer` | `number` | `1.0` | Minimum offer (granularity); offers are rounded to this |
| `seed` | `['integer', 'null']` | —` |  |
| `system_prompt` | `string` | `` | Optional system prompt override for LLM agents. |

## Metrics

- `total_payoff`
- `average_payoff`
- `avg_offer_fraction`
- `acceptance_rate`
- `offer_fairness_index`
- `ug_avg_offer_fraction`
- `ug_acceptance_rate`
- `ug_offer_fairness_index`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `nash_gap`
- `social_welfare`
- `gini_coefficient`
- `backward_induction_adherence`

## Built-in Agents

| Agent | Name | Description |
|-------|------|-------------|
| `spe` | SPE Agent | Subgame-perfect equilibrium — proposes minimum, accepts any positive offer. |
| `fair` | Fair Agent | Proposes equal split; rejects offers below 40%. |
| `greedy` | Greedy Proposer | Proposes minimum; accepts >30%. |
| `random` | Random | Random offers and random responses. |

## Example

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'ultimatum', 'players': 2, 'rounds': 10, 'total': 100.0, 'min_offer': 1.0, 'seed': 42, 'system_prompt': ''},
)
```
