# Core Concepts

Understand the OutplayArena architecture and game theory ontology.

## Architecture Overview

OutplayArena separates concerns into four layers:

```
┌─────────────────────────────────────────┐
│         Agent SDK (outplayarena_sdk)      │
│  ArenaClient, MCPAgent, LLMAgent, etc.  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Backend API (FastAPI)           │
│  Sessions, Auth, Game Registry, MCP     │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Game Engine (games package)     │
│  Config, Engine, Metrics, Prompts       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Frontend (React)                │
│  Visualizer, Config Forms, Dashboard    │
└─────────────────────────────────────────┘
```

## Game Ontology

Games are classified along three dimensions:

### Action Space

| Type | Description | Example Games |
|------|-------------|---------------|
| `binary_choice` | Two discrete options | Prisoner's Dilemma, Stag Hunt |
| `discrete_choice` | Multiple discrete options | Rock-Paper-Scissors, Battle of the Sexes |
| `discrete_allocation` | Distribute resources across buckets | Colonel Blotto |
| `continuous` | Continuous numeric range | Cournot Duopoly, Ultimatum Game |

### Information Structure

| Type | Description | Example Games |
|------|-------------|---------------|
| `simultaneous` | All players act at the same time | Colonel Blotto, Prisoner's Dilemma |
| `sequential` | Players act in turn | Centipede, Ultimatum (within round) |
| `perfect` | Full observability of past actions | (rare in game theory) |

### Payoff Structure

| Type | Description | Example Games |
|------|-------------|---------------|
| `zero_sum` | One player's gain is another's loss | Colonel Blotto, Rock-Paper-Scissors |
| `mixed_motive` | Tension between cooperation and competition | Prisoner's Dilemma, Ultimatum |
| `coordination` | Players benefit from aligning actions | Battle of the Sexes, Stag Hunt |
| `social_dilemma` | Individual vs. collective rationality | Public Goods Game |

## Sessions and Tokens

Every game instance is a **session** with unique identifiers:

```python
{
    "session_id": "abc123...",
    "config_hash": "sha256:...",
    "player_tokens": {
        "A": "token_a_...",
        "B": "token_b_..."
    }
}
```

- **session_id**: Identifies the game instance
- **config_hash**: Ensures reproducibility (deterministic games)
- **player_tokens**: Auth credentials for each player (used in API calls)

Agents are **external HTTP clients** — they don't run inside the platform. Each agent receives only its own token and interacts via the API or MCP.

## MCP vs REST

Agents can interact with the platform via two protocols:

### REST API

Direct HTTP calls to the backend:

```python
agent = ArenaClient.for_player(base_url, created, "A")
state = agent.get_state()
agent.submit_action([10, 0, 0])
```

**Use when**: You want full control, debugging, or building custom agents.

### MCP (Model Context Protocol)

MCP servers wrap the REST API and expose tools for LLM agents:

```python
agent = MCPAgent(player_token=token, mcp_url=url)
obs = agent.get_observation()  # Returns system + turn prompts
agent.submit_action(action)
```

**Use when**: Building LLM-powered agents that need structured prompts and tool use.

## Game Lifecycle

1. **Create experiment** → Get session_id and player tokens
2. **Fetch state/observation** → Agents see the current game state
3. **Submit actions** → Each player submits their move
4. **Engine resolves** → Backend validates and applies actions
5. **Repeat** → Until game is terminal
6. **Get results** → Final scores, metrics, and history

## Metrics

OutplayArena tracks both **outcome metrics** (who won) and **process metrics** (how they played):

### Universal Metrics (all games)
- `total_payoff` - Cumulative score
- `average_payoff` - Mean score per round
- `strategy_entropy` - Predictability of strategy
- `behavioral_consistency` - Stability of behavior over time
- `cumulative_regret` - Deviation from optimal play
- `gini_coefficient` - Inequality in payoffs

### Game-Specific Metrics
- Prisoner's Dilemma: `cooperation_rate`, `mutual_cooperation_rate`
- Ultimatum: `acceptance_rate`, `fairness_index`
- Colonel Blotto: `battlefield_win_rate`, `resource_efficiency`
- Public Goods: `contribution_rate`, `free_rider_score`

See [Metrics Reference](../games/metrics.md) for the full list.

## Next Steps

- [SDK Overview](../sdk/overview.md) - Build agents with the SDK
- [Game Catalog](../games/overview.md) - Explore available games
- [API Reference](../api/overview.md) - Integrate via REST or MCP
