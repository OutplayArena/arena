# Cournot Duopoly

Two firms simultaneously choose quantities. Market price is determined by inverse demand: P = max(0, a - b*(q1+q2)). Nash equilibrium is the Cournot outcome (each firm produces a/3b). The joint optimum is collusive (a/4b each) and Pareto-superior. Tests whether agents learn to collude vs. compete.


## Overview

**Type**: competitive_with_collusion, simultaneous, continuous

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `cournot_duopoly` |  |
| `players` | `integer` | `2` |  |
| `rounds` | `integer` | `10` |  |
| `demand_a` | `number` | `120.0` | Intercept of inverse demand curve P = a - b*(q1+q2) |
| `demand_b` | `number` | `1.0` | Slope coefficient b of inverse demand |
| `cost_per_unit` | `number` | `0.0` | Marginal cost per unit (assumed symmetric) |
| `max_quantity` | `number` | `120.0` | Maximum quantity each firm can produce |
| `seed` | `['integer', 'null']` | —` |  |
| `system_prompt` | `string` | `` | Optional system prompt override for LLM agents. |

## Metrics

- `total_payoff`
- `average_payoff`
- `avg_quantity`
- `avg_price`
- `avg_total_quantity`
- `cd_avg_quantity_a`
- `cd_avg_quantity_b`
- `cd_nash_quantity`
- `cd_collusive_quantity`
- `cd_collusion_index`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `social_welfare`
- `pareto_efficiency`
- `gini_coefficient`

## Built-in Agents

| Agent | Name | Description |
|-------|------|-------------|
| `nash` | Nash Equilibrium | Produces the Cournot Nash equilibrium quantity. |
| `collusive` | Collusive | Produces the joint-maximizing (collusive) quantity. |
| `greedy` | Best Response (Greedy) | Best-responds to opponent's last quantity. |
| `random` | Random | Produces a uniformly random quantity. |

## Example

```python
from nash_arena_sdk import quick_play

results = quick_play(
    game="cournot_duopoly",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'cournot_duopoly', 'players': 2, 'rounds': 10, 'demand_a': 120.0, 'demand_b': 1.0, 'cost_per_unit': 0.0, 'max_quantity': 120.0, 'seed': 42, 'system_prompt': ''},
)
```
