# Battle of the Sexes

Two players must coordinate on one of two events (Opera or Football) with conflicting preferences. Both prefer coordination over miscoordination, but each prefers a different option. Tests asymmetric coordination where agents must resolve conflicting interests through repeated play or signaling.


## Overview

**Type**: asymmetric_coordination, simultaneous, binary_choice

**Players**: 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `game` | `string` | `battle_of_the_sexes` |  |
| `players` | `integer` | `2` |  |
| `rounds` | `integer` | `10` |  |
| `payoff_preferred_a` | `number` | `3.0` | Payoff for A when both choose A's preferred option |
| `payoff_preferred_b` | `number` | `3.0` | Payoff for B when both choose B's preferred option |
| `payoff_nonpreferred` | `number` | `2.0` | Payoff for the player who got the non-preferred option (but both coordinated) |
| `payoff_mismatch` | `number` | `0.0` | Payoff when players miscoordinate |
| `option_a_label` | `string` | `opera` |  |
| `option_b_label` | `string` | `football` |  |
| `seed` | `['integer', 'null']` | —` |  |
| `system_prompt` | `string` | `` | Optional system prompt override for LLM agents. |

## Metrics

- `total_payoff`
- `average_payoff`
- `coordination_rate`
- `outcome_counts`
- `bos_coordination_rate`
- `bos_a_preferred_rate`
- `bos_b_preferred_rate`
- `equilibrium_selection_rate`
- `strategy_entropy`
- `behavioral_consistency`
- `cumulative_regret`
- `social_welfare`
- `pareto_efficiency`
- `gini_coefficient`

## Built-in Agents

| Agent | Description |
|-------|-------------|
| `always_a` | Always chooses A's preferred option. |
| `always_b` | Always chooses B's preferred option. |
| `tit_for_tat` | Mirrors opponent's last choice. |
| `mixed_nash` | Plays the mixed-strategy Nash equilibrium. |
| `random` | Chooses uniformly at random. |

## Example

```python
from nash_arena_sdk import quick_play

results = quick_play(
    game="battle_of_the_sexes",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={'game': 'battle_of_the_sexes', 'players': 2, 'rounds': 10, 'payoff_preferred_a': 3.0, 'payoff_preferred_b': 3.0, 'payoff_nonpreferred': 2.0, 'payoff_mismatch': 0.0, 'option_a_label': 'opera', 'option_b_label': 'football', 'seed': 42, 'system_prompt': ''},
)
```
