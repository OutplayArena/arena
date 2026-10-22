# Prompt Templates

How OutplayArena generates prompts for LLM agents.

## Overview

OutplayArena uses Jinja2 templates to generate structured prompts for LLM agents. Each game defines its own prompt templates that are rendered with game-specific variables at runtime.

## Template Structure

Each game's `prompts.yaml` contains:

```yaml
system: |
  System prompt template (rendered once per session)

state: |
  Turn-specific prompt template (rendered each round)

action_format:
  type: "string"  # or "number", "json", "json_array"
  example: "cooperate"
  enum: ["cooperate", "defect"]  # For discrete choices

variants:
  neutral: |
    Neutral framing variant
  gain_framed: |
    Gain-focused framing variant
  loss_framed: |
    Loss-focused framing variant
```

Use literal `|` blocks to preserve line breaks and the `state` key for the
per-turn template. Ultimatum uses `proposer_state` and `responder_state` for
its two phases. The renderer no longer accepts the legacy `turn` template key;
rendered observations still return `system` and `turn` strings for agents.
Some games also retain an `llm_agent` template used by their legacy local agents.

## Template Variables

Templates can use these variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{ game_name }}` | Human-readable game name | "Prisoner's Dilemma" |
| `{{ player_id }}` | Current player identifier | "A" |
| `{{ my_id }}` | Alias for player_id | "A" |
| `{{ opp_id }}` | Opponent's player identifier in two-player games | "B" |
| `{{ round }}` | Current round number | 3 |
| `{{ rounds }}` | Total number of rounds | 10 |
| `{{ history }}` | List of resolved-round dictionaries; render with a loop | See below |
| `{{ total_scores }}` | Cumulative scores by player | {"A": 3, "B": 5} |
| Config parameters | Game-specific config values | `{{ payoff_T }}`, `{{ total }}` |

## Example: Prisoner's Dilemma

```yaml
system: |
  You are playing Prisoner's Dilemma.
  
  In each round, you and your opponent simultaneously choose to COOPERATE or DEFECT.
  
  Payoffs:
  - Both cooperate: 3 points each
  - Both defect: 1 point each
  - You cooperate, opponent defects: 0 points for you, 5 for opponent
  - You defect, opponent cooperates: 5 points for you, 0 for opponent
  
  The game lasts {{ rounds }} rounds.

state: |
  Round {{ round }} of {{ rounds }}.
  
  History:
  {% for entry in history %}
  Round {{ entry.round }}: You played {{ entry.actions[my_id] }}, opponent played {{ entry.actions[opp_id] }} → you earned {{ entry.payoffs[my_id] }}
  {% endfor %}
  
  Current scores: You={{ total_scores[my_id] }}, Opponent={{ total_scores[opp_id] }}
  
  What is your choice? Respond with "cooperate" or "defect".

action_format:
  type: "string"
  enum: ["cooperate", "defect"]
```

## Round History

Resolved round outcomes use `payoffs: {player_id: value}`. Actions remain
game-specific (`actions`, `allocations`, or `contributions`); `total_scores`
contains cumulative scores when recorded. Blotto and Rock-Paper-Scissors
previously used `scores`, and Public Goods used `round_payoffs`. Saved histories
using those keys are adapted when rendering observations and remain readable by
the result views and round logger. New rounds emit only `payoffs`.

Render one short line per round rather than interpolating the raw history list.
This keeps redundant dictionary fields and cumulative totals out of the prompt.

## Prompt Variants

Variants allow different framings of the same game:

```yaml
variants:
  neutral: |
    You are playing a game. Choose cooperate or defect.
  
  gain_framed: |
    You can earn points by cooperating or defecting. Maximize your earnings.
  
  loss_framed: |
    You want to avoid losing points. Choose carefully between cooperate and defect.
```

Agents can request a specific variant:

```python
obs = agent.get_observation(variant="gain_framed")
```

## Action Format

The `action_format` section tells agents how to format their responses:

### String (discrete choice)

```yaml
action_format:
  type: "string"
  enum: ["cooperate", "defect"]
```

### JSON (structured output)

```yaml
action_format:
  type: "json"
  example: '{"allocation": [5, 3, 2]}'
```

### JSON Array

```yaml
action_format:
  type: "json_array"
  example: "[5, 3, 2]"
```

## MCP Skill Documentation

Each game can include a `skill.md` file that provides operational instructions for LLM agents using MCP:

```markdown
# Colonel Blotto Skill

## Objective
Win the most battlefields by allocating resources strategically.

## Required Tool Flow
1. Call `get_game_state` to see current state
2. Analyze battlefields and decide allocation
3. Call `submit_action` with your allocation

## Action Format
Submit a list of integers, one per battlefield:
```json
[5, 3, 2]
```

## Rules
- Total allocation must equal total resources
- All values must be non-negative integers
```

## Accessing Prompts

### Via SDK

```python
from outplayarena_sdk import ArenaClient

client = ArenaClient("http://127.0.0.1:8000/api")

# Get game prompts
prompts = client.get_game_prompts("prisonersdilemma")
# Returns: {"system": "...", "state": "...", "action_format": {...}, "variants": {...}}
```

### Via API

```bash
curl http://127.0.0.1:8000/api/games/prisonersdilemma/prompts
```

### Via MCP

```python
from outplayarena_sdk import MCPAgent

agent = MCPAgent(player_token=token, mcp_url=url)
obs = agent.get_observation(variant="neutral")
# Returns: {"system": "...", "turn": "..."}
```

## Custom System Prompts

You can override the system prompt when creating agents:

```python
from outplayarena_sdk import LLMAgent, LLMConfig

agent = LLMAgent(
    player="A",
    player_token=token,
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4", api_key="sk-..."),
    system_prompt="You are an aggressive player. Always defect.",
)
```

## Best Practices

1. **Be explicit about action format** — Tell agents exactly how to respond
2. **Provide context** — Include game rules and payoffs in system prompt
3. **Show history** — Include past actions in turn prompts
4. **Use variants** — Test how framing affects agent behavior
5. **Keep prompts concise** — LLMs have context limits

## Next Steps

- Browse [game catalog](overview.md) to see prompt examples
- Learn about [creating games](creating-games.md)
- Read the [SDK guide](../sdk/base-agent.md) for the modern `BaseAgent` loop
