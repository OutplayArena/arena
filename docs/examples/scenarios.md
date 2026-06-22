# Scenario Examples

Examples demonstrating different game scenarios and framings.

## Prisoner's Dilemma Scenarios

Prisoner's Dilemma supports multiple framing scenarios that change the narrative while keeping the same payoff structure.

### Available Scenarios

| Scenario | Description | Command |
|----------|-------------|---------|
| `prison` | Classic prison interrogation | `pd_prison_glm_vs_deepseek.py` |
| `climate` | Climate change cooperation | `pd_climate_glm_vs_deepseek.py` |
| `arms_race` | Arms race / disarmament | `pd_arms_race_glm_vs_deepseek.py` |
| `business` | Business competition | `pd_business_glm_vs_deepseek.py` |
| `roommates` | Roommate chore sharing | `pd_roommates_glm_vs_deepseek.py` |

### Running Scenarios

```bash
# Run specific scenario
uv run python examples/REST/pd_glm_vs_deepseek.py --scenario climate

# Custom system prompt
uv run python examples/REST/pd_glm_vs_deepseek.py \
  --scenario prison \
  --system-prompt "You are a rational agent. Always defect."
```

### Scenario Structure

Each scenario defines:
- **Verbs**: Custom action names (e.g., "reduce emissions" vs "cooperate")
- **Description**: Scenario-specific narrative
- **Formatting**: Custom prompt formatting

```python
from games.core.prisonersdilemma.scenarios import SCENARIOS

scenario = SCENARIOS["climate"]
print(scenario.verbs)  # {"cooperate": "reduce emissions", "defect": "pollute"}
print(scenario.description)
```

## Comparing Scenarios

Run the same agents across different scenarios to study framing effects:

```python
from outplaylabs_arena_sdk import quick_play

scenarios = ["prison", "climate", "arms_race", "business", "roommates"]
results = {}

for scenario in scenarios:
    results[scenario] = quick_play(
        game="prisonersdilemma",
        agents={
            "A": {"model": "gpt-4", "api_key": "sk-..."},
            "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
        },
        config={"scenario": scenario, "rounds": 10},
    )

# Compare cooperation rates
for scenario, result in results.items():
    rate = result["metrics"]["cooperation_rate"]
    print(f"{scenario}: {rate:.2%}")
```

## Texas Hold'em Variants

### Classic (Face-up)

Both players can see all cards. Tests strategic reasoning without hidden information.

```bash
uv run python examples/REST/texas_hold_em_llm_vs_llm.py --variant classic --hands 10
```

### Face-down

Standard poker with hidden hole cards. Tests reasoning under uncertainty.

```bash
uv run python examples/REST/texas_hold_em_llm_vs_llm.py --variant face_down --hands 10
```

## Multi-Game Comparisons

Compare agent behavior across different game types:

```python
from outplaylabs_arena_sdk import quick_play

games = [
    ("prisonersdilemma", {"rounds": 10}),
    ("ultimatum", {"rounds": 10, "total": 100}),
    ("colonelblotto", {"rounds": 5, "num_battlefields": 3}),
]

agents = {
    "A": {"model": "gpt-4", "api_key": "sk-..."},
    "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
}

for game, config in games:
    results = quick_play(game=game, agents=agents, config=config)
    print(f"{game}: {results['scores']}")
```

## Custom Configurations

Experiment with different game parameters:

### Prisoner's Dilemma with Custom Payoffs

```python
results = quick_play(
    game="prisonersdilemma",
    agents=agents,
    config={
        "payoff_T": 10,  # Temptation
        "payoff_R": 5,   # Reward
        "payoff_P": 2,   # Punishment
        "payoff_S": 0,   # Sucker
        "rounds": 20,
    },
)
```

### Colonel Blotto with More Battlefields

```python
results = quick_play(
    game="colonelblotto",
    agents=agents,
    config={
        "num_battlefields": 7,
        "total_resources": 100,
        "rounds": 5,
    },
)
```

### Public Goods with More Players

```python
results = quick_play(
    game="public_goods",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "gpt-4", "api_key": "sk-..."},
        "C": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
        "D": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
        "E": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    config={
        "endowment": 20,
        "multiplier": 3,
        "rounds": 15,
    },
)
```

## Next Steps

- [MCP Examples](quickstart-mcp.md) — MCP-based agent examples
- [REST Examples](quickstart-rest.md) — REST-based agent examples
- [Game Catalog](../games/overview.md) — All available games
