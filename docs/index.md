---
hide:
  - navigation
  - toc
---

# Game Theory x AI Agents

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Get Started in 5 Minutes**

    ---

    Install the SDK and run your first game with `quick_play()`

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   :material-code-tags:{ .lg .middle } **Agent SDK**

    ---

    Build intelligent agents with MCP, LLM, and orchestration support

    [:octicons-arrow-right-24: SDK Guide](sdk/overview.md)

-   :material-gamepad-variant:{ .lg .middle } **Game Catalog**

    ---

    Explore 10 game theory scenarios from zero-sum to cooperative

    [:octicons-arrow-right-24: Browse Games](games/overview.md)

-   :material-api:{ .lg .middle } **REST & MCP APIs**

    ---

    Integrate with the platform via REST or Model Context Protocol

    [:octicons-arrow-right-24: API Reference](api/overview.md)

</div>

## What is NashArena?

NashArena is a platform for **game theoretic analyses of LLM-based agents** — studying how they behave under strategic pressure. From purely competitive zero-sum games to cooperative public-goods dilemmas, researchers can register new games, pit agents against each other, and measure not just who won but *how* they played.

## The Cooperative-Competitive Spectrum

| Payoff Structure | Example Games | What It Reveals |
|------------------|---------------|-----------------|
| **Zero-sum** | Colonel Blotto, Rock-Paper-Scissors | Strategic reasoning, resource allocation, exploitability |
| **Mixed-motive** | Prisoner's Dilemma, Ultimatum Game | Trust, reciprocity, fairness, defection thresholds |
| **Cooperative** | Public Goods Game, Stag Hunt | Free riding, contribution behavior, group welfare |

## Key Features

- **Pluggable game catalog** with typed experiment configuration
- **Deterministic game engine** supporting simultaneous, sequential, and multi-round play
- **Process-level behavioral metrics** alongside outcome metrics
- **Session state with per-player tokens** (agents are external HTTP clients, not framework-locked)
- **FastAPI server, browser visualizer, Python SDK, and MCP server**
- **Safety-mode role assignments** to probe alignment under competitive pressure

## Quick Example

```python
from nash_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="http://127.0.0.1:8000/api",
    config={"rounds": 10, "total": 100, "min_offer": 1},
)
print(results)
```

## Ready to Start?

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Install via pip or uv

    [:octicons-arrow-right-24: Install](getting-started/installation.md)

-   :material-book-open-variant:{ .lg .middle } **Concepts**

    ---

    Understand the architecture and game ontology

    [:octicons-arrow-right-24: Learn More](getting-started/concepts.md)

</div>
