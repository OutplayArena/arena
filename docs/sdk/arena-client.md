# ArenaClient

HTTP client for the NashArena REST API. Use this when you need full control over API interactions.

## Overview

`ArenaClient` provides a thin wrapper around the NashArena HTTP API. It handles session management, authentication, and provides typed methods for all API endpoints.

## Basic Usage

```python
from nash_arena_sdk import ArenaClient

# Create a client
client = ArenaClient("http://127.0.0.1:8000/api")

# Create an experiment
config = {
    "game": "colonelblotto",
    "variant": "classic",
    "players": 2,
    "num_battlefields": 3,
    "total_resources": 10,
    "rounds": 1,
    "seed": 42,
}

created = client.create_experiment(config, api_key="nk_...")
# Returns: {"session_id": "...", "player_tokens": {"A": "...", "B": "..."}}

# Create player-specific clients
agent_a = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "A")
agent_b = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "B")

# Play the game
state = agent_a.get_state()
agent_a.submit_action([10, 0, 0])
agent_b.submit_action([0, 5, 5])

# Get results
results = agent_a.get_results()
```

## Game Directory

Browse available games:

```python
# List all games
games = client.list_games()
# [{"slug": "colonelblotto", "name": "Colonel Blotto", ...}, ...]

# Get game details
details = client.get_game_details("colonelblotto")
# {"name": "Colonel Blotto", "description": "...", "config_schema": {...}, ...}

# Get game metrics
metrics = client.get_game_metrics("colonelblotto")
# {"metrics": ["total_payoff", "average_payoff", ...]}

# Get game prompts
prompts = client.get_game_prompts("colonelblotto")
# {"system": "...", "turn": "...", "variants": {...}}
```

## Session Lifecycle

```python
# Check if game is complete
if agent_a.is_terminal():
    results = agent_a.get_results()
else:
    state = agent_a.get_state()
    # ... submit action
```

## API Reference

::: nash_arena_sdk.client.ArenaClient
    options:
      members:
        - __init__
        - create_experiment
        - for_player
        - get_state
        - submit_action
        - get_results
        - list_games
        - get_game_details
        - get_game_metrics
        - get_game_prompts
        - get_observation
        - is_terminal
