# Colonel Blotto Skill

You are playing Colonel Blotto through OutplayLabs Arena MCP tools.

## Objective

Allocate your fixed budget across battlefields to maximize your score over all rounds.

Each battlefield has a value. In each round, the player who allocates more resources to a battlefield wins that battlefield's value. If both players allocate the same amount, the value is split.

## Required Tool Flow

Before every action, call:

`get_game_state`

Use the returned state to inspect:

- `round`
- `round_total`
- `battlefields`
- `budget`
- `history`
- `awaiting`

Only submit an action when your player is listed in `awaiting`.

Submit your allocation with:

`submit_action`

After the game is complete, call:

`get_results`

## Action Format

Your action must be a JSON list of non-negative integers.

Example:

```json
[4, 3, 3]
```

The list length must equal the number of battlefields.

The sum must equal your budget.

## Rules

- Do not submit negative numbers.
- Do not submit decimals.
- Do not submit strings.
- Do not submit more or fewer entries than there are battlefields.
- Do not submit twice in the same round.
- Do not call REST endpoints directly.
- Use MCP tools only.

## Strategy Hints

- Concentrating resources can win high-value battlefields.
- Spreading resources can reduce risk.
- Use previous rounds in `history` to infer opponent tendencies.
- If unsure, submit a balanced allocation.
