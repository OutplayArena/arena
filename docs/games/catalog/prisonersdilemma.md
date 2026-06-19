# Prisoner's Dilemma

Classic social dilemma. Two players simultaneously choose to cooperate or defect. Mutual cooperation yields the best collective outcome (R,R), but defection is individually dominant — creating tension between personal gain and collective welfare. Supports classic and noisy variants.


## Overview

**Type**: mixed_motive, simultaneous, binary_choice

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `prisonersdilemma` |  |
| `variant` | `string` | `classic` | Game variant: classic (clean actions) or noisy (actions may randomly flip) |
| `players` | `integer` | `2` |  |
| `rounds` | `integer` | `10` |  |
| `payoff_T` | `number` | `5.0` | Temptation payoff (defect while opponent cooperates) |
| `payoff_R` | `number` | `3.0` | Reward payoff (mutual cooperation) |
| `payoff_P` | `number` | `1.0` | Punishment payoff (mutual defection) |
| `payoff_S` | `number` | `0.0` | Sucker payoff (cooperate while opponent defects) |
| `noise` | `number` | `0.0` | Probability that an action is flipped (noisy variant) |
| `seed` | `['integer', 'null']` | —` |  |
| `scenario` | `string` | `prison` | Narrative framing for LLM prompts |
| `system_prompt` | `string` | `` | System prompt for LLM agents. Uses Jinja templates ({{ payoff_T }}, {{ payoff_R }}, etc.) that are rendered with the payoff values above at runtime. |

## Metrics

- `total_payoff`
- `average_payoff`
- `cooperation_rate`
- `mutual_cooperation_rate`
- `mutual_defection_rate`
- `outcome_counts`
- `pd_outcome_counts`
- `pd_mutual_cooperation_rate`
- `pd_price_of_anarchy`
- `exploitation_rate`
- `forgiveness_rate`
- `first_move`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `nash_gap`
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
| `always_cooperate` | Always Cooperate | Always cooperates regardless of opponent's actions. |
| `always_defect` | Always Defect | Always defects regardless of opponent's actions. |
| `tit_for_tat` | Tit-for-Tat | Starts cooperating, then mirrors the opponent's last move. |
| `grim_trigger` | Grim Trigger | Cooperates until the opponent defects once, then defects forever. |
| `forgiving_tft` | Forgiving TFT | Like Tit-for-Tat but cooperates with 10% probability after opponent defects. |
| `pavlov` | Pavlov (Win-Stay/Lose-Shift) | Cooperates after mutual cooperation or after exploiting opponent; defects otherwise. |
| `random` | Random | Chooses cooperate or defect with equal probability each round. |
| `remote` | Remote Agent (LLM/MCP) | LLM-powered agent connecting via MCP server with session key. |

## Example

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="prisonersdilemma",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'prisonersdilemma', 'variant': 'classic', 'players': 2, 'rounds': 10, 'payoff_T': 5.0, 'payoff_R': 3.0, 'payoff_P': 1.0, 'payoff_S': 0.0, 'noise': 0.0, 'seed': 42, 'scenario': 'prison', 'system_prompt': ''},
)
```
