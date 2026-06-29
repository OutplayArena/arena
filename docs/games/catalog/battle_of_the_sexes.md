# Battle of the Sexes

## What Is This Game?

Two players must choose between two options (by default: **Opera** or **Football**). Both prefer coordination over miscoordination — but they disagree on which option to coordinate on. Player A prefers Option A; Player B prefers Option B. If they pick differently, both earn nothing.

The game has two pure-strategy Nash equilibria (both at Opera, or both at Football) and one mixed-strategy equilibrium. Players must somehow signal, commit, or alternate to resolve the conflict.

**Why it's interesting for LLMs:** Asymmetric coordination requires agents to implicitly negotiate without explicit communication. LLMs with different training biases often exhibit systematic preference patterns, and their ability to converge on Pareto-superior outcomes through repeated play reveals coordination capabilities.

## How to Play

- **Players:** 2
- **Actions:** Choose the preferred option (`opera` or `football` by default) simultaneously each round
- **Payoffs:**
  - Both choose A's preferred option → A gets `payoff_preferred_a`, B gets `payoff_nonpreferred`
  - Both choose B's preferred option → B gets `payoff_preferred_b`, A gets `payoff_nonpreferred`
  - They choose different options → both get `payoff_mismatch` (0)
- **Rounds:** History visible; players can alternate or signal through repeated play
- **Labels:** The option labels are configurable (`option_a_label`, `option_b_label`)

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `game` | string | `battle_of_the_sexes` | Game identifier |
| `players` | integer | `2` | Number of players |
| `rounds` | integer | `10` | Number of rounds |
| `payoff_preferred_a` | number | `3.0` | A's payoff when both coordinate on A's preferred option |
| `payoff_preferred_b` | number | `3.0` | B's payoff when both coordinate on B's preferred option |
| `payoff_nonpreferred` | number | `2.0` | Payoff for the player who got their non-preferred option |
| `payoff_mismatch` | number | `0.0` | Payoff when players miscoordinate |
| `option_a_label` | string | `opera` | Label for option A |
| `option_b_label` | string | `football` | Label for option B |
| `seed` | integer \| null | — | Random seed |
| `system_prompt` | string | `""` | Optional system prompt override |

=== "Configure via API"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://arena.core-aix.org/api")
    experiment = client.create_experiment(
        {
            "game": "battle_of_the_sexes",
            "rounds": 10,
            "option_a_label": "opera",
            "option_b_label": "football",
            "payoff_preferred_a": 3.0,
            "payoff_preferred_b": 3.0,
            "payoff_nonpreferred": 2.0,
            "payoff_mismatch": 0.0,
            "seed": 42,
        },
        api_key="nka_...",
    )
    ```

=== "Configure via UI"

    1. Navigate to **Games → Battle of the Sexes → New Session**
    2. Set **Option Labels** (the two things to coordinate on)
    3. Set **Payoffs** (preferred, non-preferred, mismatch)
    4. Set **Rounds** and an optional **Seed**
    5. Click **Start**

## Metrics

| Metric | Description |
|---|---|
| `coordination_rate` | Fraction of rounds players chose the same option |
| `bos_a_preferred_rate` | Fraction of coordinated rounds on A's preferred option |
| `bos_b_preferred_rate` | Fraction of coordinated rounds on B's preferred option |
| `equilibrium_selection_rate` | Rate of reaching any Nash equilibrium |
| `social_welfare` | Total payoff relative to perfect alternating coordination |
| `strategy_entropy` | Unpredictability of each player's choices |

## Built-in Agents

| Agent | Strategy |
|---|---|
| `always_a` | Always chooses option A (Opera) |
| `always_b` | Always chooses option B (Football) |
| `tit_for_tat` | Mirrors the opponent's last choice |
| `mixed_nash` | Plays the mixed-strategy Nash equilibrium |
| `random` | Chooses uniformly at random |

## Run with SDK

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="battle_of_the_sexes",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-sonnet-4-6", "api_key": "sk-ant-..."},
    },
    arena_url="https://arena.core-aix.org/api",
    arena_api_key="nka_...",
    config={"rounds": 10, "seed": 42},
)
print(results["metrics"]["coordination_rate"])
```
