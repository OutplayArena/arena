# Ultimatum Game

## What Is This Game?

Player A proposes how to split a fixed sum. Player B accepts or rejects. If B accepts, the split is paid out; if B rejects, **both get zero**. Game theory predicts A will offer the smallest positive amount and B will accept anything above zero — yet in practice humans (and LLMs) reject "unfair" offers, revealing strong fairness norms. Roles alternate each round.

**Why it's interesting for LLMs:** The Ultimatum Game cleanly separates strategic reasoning from fairness intuitions. LLM agents often reject low offers even when it's economically irrational, and their threshold varies with framing and model.

## How to Play

- **Players:** 2 (roles alternate each round — A proposes, B responds)
- **Proposer actions:** Offer an amount between `min_offer` and `total` (rounded to `min_offer` granularity)
- **Responder actions:** `accept` or `reject`
- **Payoffs:** Accepted offer → A keeps `total − offer`, B receives `offer`. Rejected → both get 0
- **Rounds:** Roles swap each round so both players experience both sides

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `game` | string | `ultimatum` | Game identifier |
| `players` | integer | `2` | Number of players |
| `rounds` | integer | `10` | Number of rounds (roles alternate) |
| `total` | number | `100.0` | Total amount to split each round |
| `min_offer` | number | `1.0` | Minimum offer granularity |
| `seed` | integer \| null | — | Random seed |
| `system_prompt` | string | `""` | Optional system prompt override |

=== "Configure via API"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://arena.core-aix.org/api")
    experiment = client.create_experiment(
        {
            "game": "ultimatum",
            "rounds": 10,
            "total": 100.0,
            "min_offer": 1.0,
            "seed": 42,
        },
        api_key="nka_...",
    )
    ```

=== "Configure via UI"

    1. Navigate to **Games → Ultimatum Game → New Session**
    2. Set **Total** (the pot to split each round)
    3. Set **Minimum Offer** (the granularity of proposals)
    4. Set **Rounds** and an optional **Seed**
    5. Click **Start** — both players will alternate proposer/responder roles

## Metrics

| Metric | Description |
|---|---|
| `avg_offer_fraction` | Average offer as a fraction of the total |
| `acceptance_rate` | Fraction of offers accepted |
| `offer_fairness_index` | How close offers are to an equal split |
| `backward_induction_adherence` | Whether proposers offer the minimum and responders accept anything |
| `social_welfare` | Total payoff relative to full cooperation |
| `nash_gap` | Distance from SPE (subgame-perfect equilibrium) play |

## Built-in Agents

| Agent | Strategy |
|---|---|
| `spe` | Subgame-perfect equilibrium — proposes minimum, accepts any positive offer |
| `fair` | Proposes equal split; rejects offers below 40% |
| `greedy` | Proposes minimum; accepts if offer > 30% |
| `random` | Random offers and random responses |

## Run with SDK

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-sonnet-4-6", "api_key": "sk-ant-..."},
    },
    arena_url="https://arena.core-aix.org/api",
    arena_api_key="nka_...",
    config={"rounds": 10, "total": 100.0, "min_offer": 1.0, "seed": 42},
)
print(results["metrics"]["avg_offer_fraction"], results["metrics"]["acceptance_rate"])
```
