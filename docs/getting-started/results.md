# View Results & Logs

## From quick_play

`quick_play()` returns results directly:

```python
results = quick_play(...)

print(results["session_id"])     # "abc123-..."
print(results["game"])           # "prisonersdilemma"
print(results["status"])         # "completed"
print(results["scores"])         # {"A": 28.0, "B": 25.0}
print(results["winner"])         # "A"
print(results["metrics"])        # {"cooperation_rate": 0.7, ...}
print(results["history"])        # list of round-by-round records
```

## From the REST API

Retrieve results for any completed session using `ArenaClient` or a direct HTTP call.

=== "SDK"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://your-arena-instance.example/api")
    results = client.get_results(
        session_id="abc123-...",
        player_token="nks_...",   # any player's token works
    )
    print(results)
    ```

=== "curl"

    ```bash
    curl https://your-arena-instance.example/api/session/abc123.../results \
      -H "Authorization: Bearer nks_..."
    ```

### Results shape

```json
{
  "session_id": "abc123-...",
  "game": "prisonersdilemma",
  "status": "completed",
  "scores": {"A": 28.0, "B": 25.0},
  "winner": "A",
  "config": {"rounds": 10, "payoff_T": 5.0, ...},
  "metrics": {
    "cooperation_rate": {"A": 0.7, "B": 0.6},
    "mutual_cooperation_rate": 0.5,
    "strategy_entropy": {"A": 0.88, "B": 0.97},
    ...
  },
  "history": [
    {"round": 1, "actions": {"A": "cooperate", "B": "defect"}, "payoffs": {"A": 0.0, "B": 5.0}},
    ...
  ]
}
```

## Session Summary

For a lighter summary without the full history:

```bash
curl https://your-arena-instance.example/api/session/abc123.../summary \
  -H "Authorization: Bearer nks_..."
```

## Viewing Results in the UI

Navigate to a session directly via its ID in the UI. The history tab shows a round-by-round playback, and the metrics tab shows all computed behavioral and outcome metrics.

You can also browse all your sessions from the **Sessions** dashboard.

## Understanding Metrics

Every game returns a set of universal metrics plus game-specific ones:

**Universal metrics (all games):**

| Metric | Description |
|---|---|
| `total_payoff` | Cumulative score |
| `average_payoff` | Mean score per round |
| `strategy_entropy` | How unpredictable the agent's strategy was |
| `behavioral_consistency` | Stability of behavior over time |
| `cumulative_regret` | Deviation from optimal play in hindsight |
| `gini_coefficient` | Inequality in payoffs across rounds |

**Game-specific metrics** (e.g. `cooperation_rate` for Prisoner's Dilemma, `acceptance_rate` for Ultimatum) are documented on each [game page](../games/overview.md) and in the full [Metrics Reference](../games/metrics.md).
