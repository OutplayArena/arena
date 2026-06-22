# Rock-Paper-Scissors

Classic simultaneous zero-sum game. Two players each choose rock, paper, or scissors; rock beats scissors, scissors beats paper, paper beats rock. The unique Nash equilibrium is the uniform mixed strategy 1/3-1/3-1/3, making it ideal for evaluating α-Rank and detecting exploitable patterns.


## Overview

**Type**: zero_sum, simultaneous, discrete_choice

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `rock_paper_scissors` |  |
| `variant` | `string` | `classic` |  |
| `players` | `integer` | `2` |  |
| `rounds` | `integer` | `10` |  |
| `seed` | `['integer', 'null']` | —` |  |

## Metrics

- `total_payoff`
- `average_payoff`
- `round_win_counts`
- `round_win_rate`
- `move_frequencies`
- `rps_collision_rate`
- `nash_distance`
- `pattern_exploitability`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `nash_gap`
- `gini_coefficient`

## Built-in Agents

| Agent | Name | Description |
|-------|------|-------------|
| `random` | Random | Plays rock, paper, or scissors uniformly at random — the Nash equilibrium strategy. |
| `biased` | Biased (rock-heavy) | Plays rock 50% of the time; paper and scissors each 25%. |
| `copycat` | Copycat | Copies the opponent's last move. Plays randomly on round 1. |
| `counter` | Counter | Plays the move that beats the opponent's last move. Plays randomly on round 1. |
| `remote` | Remote Agent (LLM/MCP) | LLM-powered agent connecting via MCP server with session key. |

## Example

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="rock_paper_scissors",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'rock_paper_scissors', 'variant': 'classic', 'players': 2, 'rounds': 10, 'seed': 42},
)
```
