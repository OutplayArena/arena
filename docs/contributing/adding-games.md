# Adding a New Game

New game theory scenarios are the most impactful contribution to OutplayArena. This guide walks through the full process of adding a game to the catalog.

## Overview

Each game is a directory under `games/games/core/<game_name>/` containing:

| File | Required | Purpose |
|---|---|---|
| `game.yaml` | Yes | Game metadata and config schema |
| `config.py` | Yes | Configuration dataclass |
| `engine.py` | Yes | Game engine — state, actions, payoffs |
| `metrics.yaml` | Yes | Metric declarations |
| `prompts.yaml` | Yes | LLM prompt templates |
| `metrics.py` | Yes | Metric computation |
| `agent.py` | No | Built-in deterministic agents |
| `agents.yaml` | No | Agent registry |
| `ui/` | No | Custom React components for the UI |

## Step 1: Copy the Template

```bash
cp -r games/games/_template games/games/core/my_game
```

## Step 2: Implement config.py

Define the game configuration as a dataclass. Every field appears as a parameter in the API and UI.

```python
from dataclasses import dataclass, field

@dataclass
class MyGameConfig:
    game: str = "my_game"
    players: int = 2
    rounds: int = 10
    my_param: float = 1.0   # add your game-specific parameters here
    seed: int | None = None
```

## Step 3: Implement engine.py

The engine manages game state, validates actions, applies them, and determines when the game is terminal.

```python
class MyGameEngine:
    def __init__(self, config: MyGameConfig):
        self.config = config
        self.state = self._initial_state()

    def _initial_state(self) -> dict:
        return {
            "round": 1,
            "phase": "awaiting_action",
            "awaiting": list(self.state_players()),
            "history": [],
        }

    def state_players(self) -> list[str]:
        return ["A", "B"]

    def validate_action(self, player: str, action) -> bool:
        # Return True if the action is valid for this player
        ...

    def apply_action(self, player: str, action) -> dict:
        # Record the action; resolve the round when all players have acted
        ...

    def is_terminal(self) -> bool:
        return self.state["round"] > self.config.rounds

    def results(self) -> dict:
        # Return final scores and metrics
        ...
```

## Step 4: Write game.yaml

```yaml
name: my_game
display_name: My Game
description: Brief description of the game and its strategic tension.
players:
  min: 2
  max: 2
type:
  action_space: binary_choice    # binary_choice, discrete_choice, discrete_allocation, continuous
  information: simultaneous      # simultaneous, sequential, perfect
  payoff_structure: mixed_motive # zero_sum, mixed_motive, coordination, social_dilemma, ...
config_schema:
  # JSON Schema for the config (drives the UI form)
  type: object
  properties:
    rounds:
      type: integer
      default: 10
      description: Number of rounds
    my_param:
      type: number
      default: 1.0
      description: My custom parameter
```

## Step 5: Write prompts.yaml

```yaml
system: |
  You are playing My Game. {{ description }}

  Rules:
  - Each round, you choose {{ action_description }}.
  - {{ payoff_description }}

turn: |
  Round {{ round }} of {{ total_rounds }}.
  {{ history_summary }}

  What is your action? {{ action_format_hint }}

action_format_hint: "Reply with exactly one of: OPTION_A or OPTION_B."
```

Prompts use Jinja2 templates. Available variables depend on the game state and config.

## Step 6: Write metrics.yaml and metrics.py

Declare the metrics your game tracks:

```yaml
# metrics.yaml
metrics:
  - name: my_metric
    description: Description of what this measures
    type: float   # float, int, dict, list
    per_player: true
```

Implement computation in `metrics.py`:

```python
def compute_metrics(history: list[dict], config: MyGameConfig) -> dict:
    my_metric = ...  # compute from history
    return {
        "my_metric": {"A": 0.7, "B": 0.3},
        # also include universal metrics
        "total_payoff": ...,
        "strategy_entropy": ...,
    }
```

## Step 7: Register the Game

Add your game to `games/games/__init__.py`:

```python
from games.core.my_game import config, engine, metrics

GAME_REGISTRY["my_game"] = {
    "config": config.MyGameConfig,
    "engine": engine.MyGameEngine,
    "metrics": metrics.compute_metrics,
}
```

## Step 8: Write Tests

```python
# games/games/core/my_game/tests/test_engine.py

def test_initial_state():
    cfg = MyGameConfig()
    eng = MyGameEngine(cfg)
    assert eng.state["round"] == 1
    assert "A" in eng.state["awaiting"]

def test_valid_action():
    ...

def test_apply_action():
    ...

def test_is_terminal():
    ...

def test_results():
    ...
```

Run:

```bash
uv run pytest games/games/core/my_game/
```

## Step 9: Verify Registration

```bash
# Start the backend (see contributing/docker-compose.md)
curl http://localhost:8000/api/games/my_game
```

## Step 10: Add Documentation

Add a page for your game in `docs/games/catalog/my_game.md` following the [existing game page template](../games/catalog/colonelblotto.md). Add it to the `nav` in `mkdocs.yml` under the Games section.

## Optional: Add Built-in Agents

Built-in agents let users benchmark against deterministic strategies from the UI. Add them in `agent.py` and register them in `agents.yaml`:

```yaml
# agents.yaml
agents:
  - id: always_a
    name: Always A
    description: Always chooses option A.
    class: agents.AlwaysAAgent
```

## Optional: Add Custom UI Components

Add React components to `ui/` for custom in-game visualization (live view, config form, history view). Follow the pattern of existing game UI components.
