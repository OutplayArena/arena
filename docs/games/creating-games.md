# Creating Games

Guide to creating new games for NashArena.

## Overview

NashArena's game catalog is extensible. You can add new games by implementing a standard interface. Each game consists of:

- **Configuration** — Game parameters and validation
- **Engine** — Game logic and state management
- **Metrics** — Game-specific metrics computation
- **Prompts** — LLM prompt templates
- **UI Components** — React components for the frontend
- **Metadata** — YAML files describing the game

## Directory Structure

```
games/games/core/my_game/
├── __init__.py          # Package exports
├── config.py            # Game configuration
├── engine.py            # Game engine
├── metrics.py           # Metrics computation
├── agent.py             # Built-in agents (optional)
├── game.yaml            # Game metadata
├── metrics.yaml         # Metrics list
├── prompts.yaml         # LLM prompts
├── agents.yaml          # Agent registry
├── skill.md             # MCP skill documentation
├── tests/
│   ├── test_engine.py
│   └── test_metrics.py
└── ui/
    ├── ConfigForm.tsx   # Configuration form
    └── LiveView.tsx     # Live game view
```

## Step-by-Step Guide

### 1. Create game.yaml

Define game metadata and configuration schema:

```yaml
name: "My Game"
version: "1.0.0"
status: "stable"  # or "experimental"
author: "Your Name"
description: |
  A brief description of the game and its strategic structure.

tags:
  - coordination
  - mixed-motive

ontology:
  action_space: "binary_choice"  # binary_choice, discrete_choice, discrete_allocation, continuous
  information_structure: "simultaneous"  # simultaneous, sequential, perfect
  payoff_structure: "mixed_motive"  # zero_sum, mixed_motive, coordination, social_dilemma
  timing: "multi_round"  # multi_round, sequential

players:
  min: 2
  max: 2

config_schema:
  game:
    type: "string"
    const: "my_game"
  players:
    type: "integer"
    const: 2
  rounds:
    type: "integer"
    minimum: 1
    default: 10
  seed:
    type: "integer"
    default: null

example_config:
  game: "my_game"
  players: 2
  rounds: 10
  seed: 42
```

### 2. Implement config.py

```python
from dataclasses import dataclass
from games.core.base import GameConfig

@dataclass(frozen=True)
class MyGameConfig(GameConfig):
    game: str = "my_game"
    players: int = 2
    rounds: int = 10
    seed: int | None = None
    
    def __post_init__(self):
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
    
    def player_ids(self) -> list[str]:
        return ["A", "B"]

def config_from_dict(data: dict) -> MyGameConfig:
    return MyGameConfig(**data)
```

### 3. Implement engine.py

```python
from dataclasses import dataclass
from games.core.base import GameEngine

@dataclass
class MyGameState:
    round: int = 0
    history: list = None
    scores: dict = None
    
    def __post_init__(self):
        if self.history is None:
            self.history = []
        if self.scores is None:
            self.scores = {"A": 0, "B": 0}

class MyGameEngine(GameEngine):
    def initial_state(self) -> MyGameState:
        return MyGameState()
    
    def validate_action(self, action) -> bool:
        # Validate action format
        return isinstance(action, str) and action in ["option1", "option2"]
    
    def apply_action(self, state: MyGameState, player: str, action) -> MyGameState:
        # Apply action and return new state
        new_state = MyGameState(
            round=state.round + 1,
            history=state.history + [{"player": player, "action": action}],
            scores=state.scores.copy()
        )
        # Update scores based on action
        return new_state
    
    def is_terminal(self, state: MyGameState) -> bool:
        return state.round >= self.config.rounds
    
    def compute_results(self, state: MyGameState, session_id: str, config_hash: str) -> dict:
        return {
            "session_id": session_id,
            "config_hash": config_hash,
            "scores": state.scores,
            "winner": max(state.scores, key=state.scores.get),
            "history": state.history,
        }
    
    def public_state(self, state: MyGameState, config, session_id: str, config_hash: str) -> dict:
        return {
            "round": state.round,
            "total_rounds": config.rounds,
            "history": state.history,
            "scores": state.scores,
        }
```

### 4. Implement metrics.py

```python
from games.core.base import GameMetrics

class MyGameMetrics(GameMetrics):
    def compute(self, history: list, total_scores: dict) -> dict:
        metrics = {
            "total_payoff": total_scores,
            "average_payoff": {p: s / len(history) for p, s in total_scores.items()},
        }
        # Add game-specific metrics
        return metrics
```

### 5. Create prompts.yaml

```yaml
system: |
  You are playing {{ game_name }}.
  {{ game_description }}

state: |
  Round {{ round }} of {{ rounds }}.
  
  History:
  {{ history }}
  
  Current scores: A={{ scores.A }}, B={{ scores.B }}
  
  Choose your action: "option1" or "option2"

action_format:
  type: "string"
  enum: ["option1", "option2"]
```

### 6. Create metrics.yaml

```yaml
metrics:
  - total_payoff
  - average_payoff
  - strategy_entropy
  - behavioral_consistency
  # Add game-specific metrics
```

### 7. Create agents.yaml (optional)

```yaml
agents:
  - id: "option1_agent"
    name: "Option 1 Agent"
    description: "Always chooses option 1"
    class: "Option1Agent"
```

### 8. Implement built-in agents (optional)

```python
from games.core.base import GameAgent

class Option1Agent(GameAgent):
    def act(self, history: list) -> str:
        return "option1"
```

### 9. Register the game

Add to `games/games/__init__.py`:

```python
from games.core.my_game import config, engine, metrics

GAME_REGISTRY["my_game"] = {
    "config": config.MyGameConfig,
    "engine": engine.MyGameEngine,
    "metrics": metrics.MyGameMetrics,
}
```

### 10. Create UI components (optional)

Create React components in `ui/`:

```tsx
// ui/ConfigForm.tsx
export default function MyGameConfigForm({ config, onChange }) {
  return (
    <div>
      <input
        type="number"
        value={config.rounds}
        onChange={(e) => onChange({...config, rounds: e.target.value})}
      />
    </div>
  );
}
```

## Testing

Write tests for your game:

```python
# tests/test_engine.py
def test_initial_state():
    engine = MyGameEngine(MyGameConfig())
    state = engine.initial_state()
    assert state.round == 0

def test_valid_action():
    engine = MyGameEngine(MyGameConfig())
    assert engine.validate_action("option1")
    assert not engine.validate_action("invalid")
```

Run tests:

```bash
uv run pytest games/games/core/my_game/tests/
```

## Template

A complete template is available at `games/games/_template/`. Copy it to get started:

```bash
cp -r games/games/_template games/games/core/my_game
```

## Next Steps

- Browse [existing games](overview.md) for examples
- Read about [prompt templates](prompts.md)
- Check the [metrics reference](metrics.md)
