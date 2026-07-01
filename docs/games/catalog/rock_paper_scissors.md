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
| `interactive` | Interactive (Human) | You play directly via the Live View panel. |

## How to Play

You are playing Rock-Paper-Scissors through OutplayArena MCP tools.

## Objective

Choose rock, paper, or scissors each round to maximise your cumulative score
over all rounds.

Scoring per round: win = +1, tie = 0, loss = -1.

## Required Tool Flow

Before every action, call:

`get_game_state`

Use the returned state to inspect:

- `round`
- `round_total`
- `awaiting`
- `total_scores`
- `history`

Only submit an action when your player is listed in `awaiting`.

Submit your move with:

`submit_action`

After the game is complete, call:

`get_results`

## Action Format

Your action must be exactly one of the following strings:

- `"rock"`
- `"paper"`
- `"scissors"`

Example:

```json
"rock"
```

## Rules

- Rock beats scissors
- Scissors beats paper
- Paper beats rock
- Ties score 0
- Do not submit any string other than rock, paper, or scissors
- Do not call REST endpoints directly
- Use MCP tools only

## Strategy

The unique Nash equilibrium is to play each option with equal probability (1/3).
Any deviation from uniform play is exploitable by an opponent who observes your
history. Check `history` for your opponent's move frequency imbalances before
committing to a counter-strategy.

## Example

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="rock_paper_scissors",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'rock_paper_scissors', 'variant': 'classic', 'players': 2, 'rounds': 10, 'seed': 42},
)
```
