# Rock-Paper-Scissors Skill

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
