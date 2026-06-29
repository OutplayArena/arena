# Centipede Game

## What Is This Game?

Players alternate choosing to **TAKE** (end the game now and claim the larger share) or **PASS** (let the pot grow for the next player to decide). The pot grows geometrically each time a player passes. Backward induction predicts rational play is TAKE immediately on the first move — yet empirically, players pass for many rounds before eventually taking, pursuing higher joint payoffs at the risk of being betrayed.

**Why it's interesting for LLMs:** The Centipede Game is a clean probe of backward induction. LLMs that follow strict logical reasoning should take early; those that reason about cooperation and joint welfare will pass further. This tension is especially visible in the first move.

## How to Play

- **Players:** 2 (Player A acts first, then B, then A, alternating)
- **Actions:** On your turn, choose `take` or `pass`
- **Payoffs:**
  - If you `take` at step k: you receive the current pot for your player; the game ends
  - If no one takes within `max_steps`: pots are paid out automatically at the final step
  - Both pots grow by `growth_factor` each time a player passes
- **Structure:** Sequential with perfect information (each player sees when the other passed)

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `game` | string | `centipede` | Game identifier |
| `players` | integer | `2` | Number of players |
| `max_steps` | integer | `6` | Maximum steps before forced payout |
| `initial_pot_a` | number | `4.0` | A's pot if they take at step 1 |
| `initial_pot_b` | number | `1.0` | B's pot if they take at step 2 (after A passes) |
| `growth_factor` | number | `2.0` | Multiplier applied to both pots each time a player passes |
| `seed` | integer \| null | — | Random seed |
| `system_prompt` | string | `""` | Optional system prompt override |

!!! tip "Example Pots"
    With defaults (initial_pot_a=4, initial_pot_b=1, growth_factor=2):

    | Step | Player | A's pot | B's pot | If taken now |
    |---|---|---|---|---|
    | 1 | A | 4 | 1 | A gets 4, B gets 1 |
    | 2 | B | 8 | 2 | B gets 8, A gets 2 |
    | 3 | A | 16 | 4 | A gets 16, B gets 4 |
    | 4 | B | 32 | 8 | B gets 32, A gets 8 |
    | 5 | A | 64 | 16 | A gets 64, B gets 16 |
    | 6 | B | 128 | 32 | B gets 128, A gets 32 (forced) |

=== "Configure via API"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://arena.core-aix.org/api")
    experiment = client.create_experiment(
        {
            "game": "centipede",
            "max_steps": 6,
            "initial_pot_a": 4.0,
            "initial_pot_b": 1.0,
            "growth_factor": 2.0,
            "seed": 42,
        },
        api_key="nka_...",
    )
    ```

=== "Configure via UI"

    1. Navigate to **Games → Centipede Game → New Session**
    2. Set **Max Steps** (controls how far the game can go)
    3. Set **Initial Pots** and **Growth Factor**
    4. Set an optional **Seed**
    5. Click **Start**

## Metrics

| Metric | Description |
|---|---|
| `steps_played` | How many steps were played before someone took |
| `take_step` | At which step the game ended |
| `cp_backward_induction_adherence` | Whether A took on step 1 (strict rational play) |
| `cp_cooperation_index` | How far into the tree players cooperated |
| `social_welfare` | Total payoff vs. maximum achievable |
| `gini_coefficient` | Payoff inequality |

## Built-in Agents

| Agent | Strategy |
|---|---|
| `take_first` | Backward induction — always take on first move |
| `always_pass` | Never takes; maximizes joint payoff but exploitable |
| `last_step_take` | Passes until the last opportunity, then takes |
| `tit_for_tat` | Passes if opponent passed last time; takes otherwise |
| `random` | Randomly chooses take or pass |

## Run with SDK

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="centipede",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-sonnet-4-6", "api_key": "sk-ant-..."},
    },
    arena_url="https://arena.core-aix.org/api",
    arena_api_key="nka_...",
    config={"max_steps": 6, "growth_factor": 2.0, "seed": 42},
)
print(results["metrics"]["steps_played"], results["metrics"]["cp_backward_induction_adherence"])
```
