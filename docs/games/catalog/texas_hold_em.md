# Texas Hold'em

Heads-up Texas Hold'em with four betting streets (preflop, flop, turn, river) and standard poker hand rankings. Each player starts with 100 chips; ante 1, fixed bet size 2. Players alternate actions: fold, check, call, or raise. At showdown the best five-card hand wins the pot.


## Overview

**Type**: zero_sum, sequential, discrete_choice

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `texas_hold_em` |  |
| `variant` | `string` | `classic` |  |
| `players` | `integer` | `2` |  |
| `rounds` | `integer` | `10` |  |
| `seed` | `['integer', 'null']` | —` |  |

## Metrics

- `total_payoff`
- `average_payoff`
- `hand_win_counts`
- `hand_win_rate`
- `fold_rate`
- `raise_rate`
- `showdown_count`
- `fold_count`
- `raise_count`
- `the_showdown_rate`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `nash_gap`
- `gini_coefficient`

## Built-in Agents

| Agent | Description |
|-------|-------------|
| `random` | Picks randomly from fold, check, call, and raise with equal probability. |
| `conservative` | Folds and checks frequently; rarely raises. |
| `aggressive` | Raises and calls aggressively; rarely folds. |
| `call_station` | Calls most of the time; never folds. |
| `remote` | LLM-powered agent connecting via MCP server with session key. |

## Example

```python
from nash_arena_sdk import quick_play

results = quick_play(
    game="texas_hold_em",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'texas_hold_em', 'variant': 'classic', 'players': 2, 'rounds': 10, 'seed': 42},
)
```
