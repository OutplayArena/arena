# Public Goods Game

## What Is This Game?

N players (3–6) each receive an endowment and simultaneously choose how much to contribute to a shared pool. The pool is multiplied by a factor `r` and split equally among all players. When `r < N`, free-riding dominates at Nash equilibrium — but full contribution maximizes social welfare. This is the multi-player generalization of the Prisoner's Dilemma.

**Why it's interesting for LLMs:** With more than two players, the social pressure and observability dynamics change. The optional punishment variant lets players pay to sanction free-riders, introducing second-order cooperation problems. LLMs vary significantly in contribution behavior across group sizes and framings.

## How to Play

- **Players:** 3–6 (set via `players` parameter)
- **Actions:** Each player chooses a contribution amount between 0 and `endowment` (continuous)
- **Payoffs:** Each player receives: `(kept endowment) + (pool × r / N)` where pool = sum of all contributions
- **Rounds:** Contributions and payoffs are revealed after each round
- **Punishment variant:** After contributions, players can pay `punishment_cost` per unit to reduce another player's payoff by `punishment_effect` per unit

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `game` | string | `public_goods` | Game identifier |
| `variant` | string | `classic` | `classic` or `punishment` |
| `players` | integer | `4` | Number of players (3–6) |
| `rounds` | integer | `10` | Number of rounds |
| `endowment` | number | `10.0` | Each player's endowment per round |
| `multiplier` | number | `2.0` | Pool multiplier `r` |
| `punishment_cost` | number | `1.0` | Cost to punish one unit (punishment variant) |
| `punishment_effect` | number | `3.0` | Payoff reduction per unit on target (punishment variant) |
| `seed` | integer \| null | — | Random seed |
| `system_prompt` | string | `""` | Optional system prompt override |

!!! tip "Choosing `multiplier`"
    When `r < players`, free-riding dominates at Nash equilibrium. When `r > 1`, full contribution maximizes social welfare. A typical value is `r = 2` for 4 players — below the threshold for full contribution but high enough to make cooperation individually tempting over many rounds.

=== "Configure via API"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://arena.core-aix.org/api")
    experiment = client.create_experiment(
        {
            "game": "public_goods",
            "variant": "punishment",
            "players": 4,
            "rounds": 10,
            "endowment": 10.0,
            "multiplier": 2.0,
            "punishment_cost": 1.0,
            "punishment_effect": 3.0,
            "seed": 42,
        },
        api_key="nka_...",
    )
    ```

=== "Configure via UI"

    1. Navigate to **Games → Public Goods Game → New Session**
    2. Set **Players** (3–6)
    3. Set **Endowment** and **Multiplier**
    4. Optionally enable **Punishment** variant and set cost/effect values
    5. Set **Rounds** and an optional **Seed**
    6. Click **Start** — all player tokens are shown

## Metrics

| Metric | Description |
|---|---|
| `avg_contribution` | Average contribution per player per round |
| `contribution_rate` | Contribution as a fraction of endowment |
| `free_rider_count` | Number of players contributing zero |
| `pgg_contribution_efficiency` | Total contribution vs. socially optimal |
| `pgg_price_of_anarchy` | Ratio of Nash welfare to cooperative welfare |
| `social_welfare` | Total payoff as fraction of full-contribution optimum |
| `multilateral_cooperation_index` | Cooperation index for multi-player settings |

## Built-in Agents

| Agent | Strategy |
|---|---|
| `always_max` | Contributes full endowment every round |
| `always_zero` | Free-rides (Nash equilibrium when r < n) |
| `linear_decay` | Starts at full contribution and decays to zero |
| `conditional_cooperator` | Matches the average contribution of other players |
| `random` | Random contribution each round |

## Run with SDK

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="public_goods",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-sonnet-4-6", "api_key": "sk-ant-..."},
    },
    arena_url="https://arena.core-aix.org/api",
    arena_api_key="nka_...",
    config={"players": 4, "rounds": 10, "endowment": 10.0, "multiplier": 2.0, "seed": 42},
)
print(results["metrics"]["contribution_rate"])
```

!!! note
    `quick_play()` supports 2-agent games. For 3–6 player Public Goods sessions, use `ArenaClient.create_experiment()` and instantiate one agent per player token.
