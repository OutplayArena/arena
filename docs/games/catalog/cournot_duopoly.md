# Cournot Duopoly

## What Is This Game?

Two firms simultaneously choose production quantities. Market price is determined by inverse demand: `P = max(0, a − b × (q1 + q2))`. Each firm maximizes its own profit. The Nash equilibrium (Cournot outcome) has each firm producing `a / (3b)`. If they collude (cartelize), each produces `a / (4b)` and earns more — but collusion is individually unstable because each firm has an incentive to defect.

**Why it's interesting for LLMs:** The Cournot Duopoly is a continuous-action analog of the Prisoner's Dilemma in an economic context. LLMs can converge on collusion through repeated play, defect strategically, or fail to find the Nash quantity entirely.

## How to Play

- **Players:** 2 (Firm A and Firm B)
- **Actions:** Each firm simultaneously chooses a quantity `q` between 0 and `max_quantity` (continuous)
- **Payoffs:** Firm profit = `P × q − cost_per_unit × q`, where `P = max(0, a − b × (q1 + q2))`
- **Rounds:** Quantities and prices are revealed after each round
- **Key benchmarks:**
  - Cournot Nash: each firm produces `a / (3b)` → less total output, higher price
  - Collusive: each firm produces `a / (4b)` → even less output, even higher price, higher individual profit
  - Competitive: each firm produces `a / (2b)` → more output, zero profit

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `game` | string | `cournot_duopoly` | Game identifier |
| `players` | integer | `2` | Number of players |
| `rounds` | integer | `10` | Number of rounds |
| `demand_a` | number | `120.0` | Demand intercept (`a`) |
| `demand_b` | number | `1.0` | Demand slope (`b`) |
| `cost_per_unit` | number | `0.0` | Marginal cost per unit |
| `max_quantity` | number | `120.0` | Maximum quantity each firm can produce |
| `seed` | integer \| null | — | Random seed |
| `system_prompt` | string | `""` | Optional system prompt override |

With defaults: Nash quantity = 40 each, collusive quantity = 30 each.

=== "Configure via API"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://arena.core-aix.org/api")
    experiment = client.create_experiment(
        {
            "game": "cournot_duopoly",
            "rounds": 10,
            "demand_a": 120.0,
            "demand_b": 1.0,
            "cost_per_unit": 0.0,
            "max_quantity": 120.0,
            "seed": 42,
        },
        api_key="nka_...",
    )
    ```

=== "Configure via UI"

    1. Navigate to **Games → Cournot Duopoly → New Session**
    2. Set **Demand Parameters** (a and b) to define the market
    3. Set **Marginal Cost** and **Max Quantity**
    4. Set **Rounds** and an optional **Seed**
    5. Click **Start**

## Metrics

| Metric | Description |
|---|---|
| `avg_quantity` | Average quantity produced per firm per round |
| `avg_price` | Average market price |
| `avg_total_quantity` | Sum of both firms' average quantities |
| `cd_collusion_index` | How close to the collusive outcome (1 = full collusion) |
| `cd_nash_quantity` | Theoretical Nash quantity for reference |
| `cd_collusive_quantity` | Theoretical collusive quantity for reference |
| `social_welfare` | Total profit as fraction of collusive maximum |
| `pareto_efficiency` | Whether outcomes are Pareto-optimal |

## Built-in Agents

| Agent | Strategy |
|---|---|
| `nash` | Produces the Cournot Nash equilibrium quantity |
| `collusive` | Produces the joint-profit-maximizing (collusive) quantity |
| `greedy` | Best-responds to the opponent's last quantity |
| `random` | Produces a uniformly random quantity |

## Run with SDK

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="cournot_duopoly",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-sonnet-4-6", "api_key": "sk-ant-..."},
    },
    arena_url="https://arena.core-aix.org/api",
    arena_api_key="nka_...",
    config={"rounds": 10, "demand_a": 120.0, "demand_b": 1.0, "seed": 42},
)
print(results["metrics"]["cd_collusion_index"])
```
