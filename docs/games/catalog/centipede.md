# Centipede Game

A sequential game where two players alternately choose to TAKE (end the game) or PASS (increase the pot). Backward induction predicts TAKE immediately, but empirically cooperation persists. A clean probe of whether LLMs follow backward induction or maintain cooperation for joint gain.


## Overview

**Type**: sequential_cooperation, perfect, binary_choice

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `centipede` |  |
| `players` | `integer` | `2` |  |
| `max_steps` | `integer` | `6` | Maximum number of steps before forced payout |
| `initial_pot_a` | `number` | `4.0` | Initial pot value for player A if they take immediately |
| `initial_pot_b` | `number` | `1.0` | Initial pot value for player B if they take immediately |
| `growth_factor` | `number` | `2.0` | Factor by which both pots grow each time a player passes |
| `seed` | `['integer', 'null']` | —` |  |
| `system_prompt` | `string` | `` | Optional system prompt override for LLM agents. |

## Metrics

- `total_payoff`
- `steps_played`
- `game_ended_early`
- `take_step`
- `cp_steps_played`
- `cp_take_at_step`
- `cp_backward_induction_adherence`
- `cp_cooperation_index`
- `backward_induction_adherence`
- `strategy_entropy`
- `cumulative_regret`
- `social_welfare`
- `gini_coefficient`

## Built-in Agents

| Agent | Name | Description |
|-------|------|-------------|
| `take_first` | Take First (SPE) | Backward induction — always take on first move. |
| `always_pass` | Always Pass | Never takes; maximizes joint payoff (cooperative but exploitable). |
| `last_step_take` | Last Step Take | Passes until the last opportunity, then takes. |
| `tit_for_tat` | Tit for Tat | Passes if opponent passed last time, takes otherwise. |
| `random` | Random | Chooses randomly between take and pass. |

## Example

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="centipede",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'centipede', 'players': 2, 'max_steps': 6, 'initial_pot_a': 4.0, 'initial_pot_b': 1.0, 'growth_factor': 2.0, 'seed': None, 'system_prompt': ''},
)
```
