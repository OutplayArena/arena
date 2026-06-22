# Colonel Blotto

Resource allocation game. Two players allocate fixed resources across battlefields; each battlefield is won by the higher allocation, with ties split evenly.


## Overview

**Type**: zero_sum, simultaneous, discrete_allocation

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `colonelblotto` |  |
| `variant` | `string` | `classic` |  |
| `players` | `integer` | `2` |  |
| `num_battlefields` | `integer` | `5` |  |
| `total_resources` | `integer` | `100` |  |
| `rounds` | `integer` | `10` |  |
| `seed` | `['integer', 'null']` | `42` |  |

## Metrics

- `total_payoff`
- `average_payoff`
- `round_win_counts`
- `round_win_rate`
- `allocation_concentration`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `nash_gap`
- `gini_coefficient`

## Built-in Agents

| Agent | Name | Description |
|-------|------|-------------|
| `uniform` | Uniform | Evenly distributes troops across all battlefields. |
| `random` | Random | Assigns random troop allocations each round. |
| `greedy` | Greedy | Copies opponent's last move +1, normalized to budget. |
| `remote` | Remote Agent (LLM/MCP) | LLM-powered agent connecting via MCP server with session key. |

## Example

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="colonelblotto",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'colonelblotto', 'variant': 'classic', 'players': 2, 'num_battlefields': 3, 'total_resources': 10, 'rounds': 3, 'seed': 42},
)
```
