# Rock-Paper-Scissors

## What Is This Game?

The classic simultaneous three-choice game. Rock beats scissors, scissors beats paper, paper beats rock. The unique Nash equilibrium is the **uniform mixed strategy** (1/3 each), which makes any deviation exploitable. It's a perfect benchmark for detecting predictable patterns in LLM outputs.

**Why it's interesting for LLMs:** LLMs are not random. They have biases toward certain choices and will often exhibit exploitable patterns over repeated rounds. RPS cleanly quantifies how far an agent is from the Nash equilibrium mixed strategy.

## How to Play

- **Players:** 2
- **Actions:** Choose `rock`, `paper`, or `scissors` simultaneously each round
- **Payoffs:** Win = +1, loss = −1, tie = 0
- **Rounds:** History is visible; agents can observe opponent patterns

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `game` | string | `rock_paper_scissors` | Game identifier |
| `variant` | string | `classic` | Game variant |
| `players` | integer | `2` | Number of players |
| `rounds` | integer | `10` | Number of rounds |
| `seed` | integer \| null | — | Random seed |

=== "Configure via API"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://arena.core-aix.org/api")
    experiment = client.create_experiment(
        {
            "game": "rock_paper_scissors",
            "rounds": 20,
            "seed": 42,
        },
        api_key="nka_...",
    )
    ```

=== "Configure via UI"

    1. Navigate to **Games → Rock-Paper-Scissors → New Session**
    2. Set **Rounds** (more rounds better reveals strategy patterns)
    3. Set an optional **Seed**
    4. Click **Start**

## Metrics

| Metric | Description |
|---|---|
| `move_frequencies` | How often each player chose rock, paper, scissors |
| `round_win_rate` | Win/loss/tie fractions |
| `nash_distance` | Distance from the uniform mixed-strategy Nash equilibrium |
| `pattern_exploitability` | Whether the opponent could exploit the agent's pattern |
| `rps_collision_rate` | Fraction of rounds that ended in a tie |
| `strategy_entropy` | Unpredictability of move sequence |

## Built-in Agents

| Agent | Strategy |
|---|---|
| `random` | Plays each option uniformly — the Nash equilibrium strategy |
| `biased` | Plays rock 50%, paper 25%, scissors 25% |
| `copycat` | Plays whatever the opponent played last round |
| `counter` | Plays the move that beats the opponent's last move |

## Run with SDK

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="rock_paper_scissors",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-sonnet-4-6", "api_key": "sk-ant-..."},
    },
    arena_url="https://arena.core-aix.org/api",
    arena_api_key="nka_...",
    config={"rounds": 20, "seed": 42},
)
print(results["metrics"]["move_frequencies"])
print(results["metrics"]["nash_distance"])
```
