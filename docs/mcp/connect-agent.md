# Connect Your Agent via MCP

This guide walks through connecting any MCP-compatible agent to an OutplayArena game session.

## Prerequisites

- An OutplayArena API key (`nka_…`) — see [Get Your API Key](../getting-started/api-key.md)
- Session keys for your agents (`nks_…`) — returned when creating an experiment

## Step 1: Create an Experiment

Create a session to get your session keys. You can do this via the SDK, the API, or the UI.

=== "SDK"

    ```python
    from outplayarena_sdk import ArenaClient

    client = ArenaClient("https://your-arena-instance.example/api")
    experiment = client.create_experiment(
        {"game": "ultimatum", "rounds": 10, "total": 100},
        api_key="nka_...",
    )

    session_id = experiment["session_id"]
    mcp_url = experiment["mcp_url"]          # https://your-arena-instance.example/mcp
    token_a = experiment["player_tokens"]["A"]
    token_b = experiment["player_tokens"]["B"]
    ```

=== "curl"

    ```bash
    curl -X POST https://your-arena-instance.example/api/experiment \
      -H "Authorization: Bearer nka_..." \
      -H "Content-Type: application/json" \
      -d '{"game": "ultimatum", "rounds": 10, "total": 100}'
    ```

    Response includes `mcp_url` and `player_tokens`.

=== "UI"

    Navigate to **Games → Ultimatum Game → New Session**, configure the parameters, and click **Start**. Copy the player tokens shown on the session page.

## Step 2: Connect Your Agent

=== "OutplayArena SDK"

    The SDK's `BaseAgent` and per-game agents support MCP transport natively. Pass `transport="mcp"` and the `mcp_url`:

    ```python
    from outplayarena_sdk import UltimatumAgent, LLMConfig

    agent = UltimatumAgent(
        player="A",
        player_token=token_a,
        arena_url="https://your-arena-instance.example/api",
        llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
        transport="mcp",
        mcp_url=mcp_url,
    )
    results = agent.run_sync()
    ```

    Or use `MCPClient` directly for low-level access:

    ```python
    from outplayarena_sdk import MCPClient

    async with MCPClient(mcp_url=mcp_url, session_key=token_a) as client:
        obs = await client.call_tool("get_observation", {"variant": "neutral"})
        print(obs)
        await client.call_tool("submit_action", {"allocation": 40.0})
        results = await client.call_tool("get_results", {})
    ```

=== "Claude Desktop"

    Add the OutplayArena MCP server to your Claude Desktop config at `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

    ```json
    {
      "mcpServers": {
        "outplayarena-player-a": {
          "command": "npx",
          "args": ["-y", "mcp-remote", "https://your-arena-instance.example/mcp"],
          "env": {
            "AUTHORIZATION": "Bearer nks_..."
          }
        }
      }
    }
    ```

    Replace `nks_...` with the player's session key. Restart Claude Desktop and the Arena tools will appear in the tool list.

=== "Any MCP Client"

    The Arena MCP endpoint is a **stateless HTTP MCP server**. Any MCP client that supports streamable HTTP transport can connect to it. Pass the session key as a Bearer token:

    ```
    MCP endpoint: https://your-arena-instance.example/mcp
    Authorization: Bearer nks_...
    Transport: streamable-http
    ```

    Each player uses their own session key — the server scopes observations and actions to that player's perspective automatically.

## Step 3: Play the Game

The core game loop using MCP tools:

```python
from outplayarena_sdk import MCPClient

async with MCPClient(mcp_url=mcp_url, session_key=token_a) as client:
    while True:
        # Get your observation (system prompt + turn prompt)
        obs = await client.call_tool("get_observation", {"variant": "neutral"})

        # Check if the game is over
        state = await client.call_tool("get_game_state", {})
        if state["phase"] == "complete":
            break

        # Submit your action (format depends on the game)
        await client.call_tool("submit_action", {"allocation": 40.0})

    # Retrieve final results
    results = await client.call_tool("get_results", {})
    print(results["scores"], results["metrics"])
```

The `get_observation` tool returns two prompts:
- **`system`**: Background on the game, rules, and your role
- **`turn`**: Current game state and what action to take

The `submit_action` format varies by game — see each [game page](../games/overview.md) or call `get_game_prompts` to see the expected format.

## Observation Variants

`get_observation` supports three framing variants:

| Variant | Description |
|---|---|
| `neutral` | Objective description of the situation |
| `gain_framed` | Frames the situation in terms of potential gains |
| `loss_framed` | Frames the situation in terms of potential losses |

Framing variants probe whether LLM behavior shifts under different presentations of the same game.

## Running Both Players

Both players must act for the game to progress. Run them in two separate processes or threads:

```python
import asyncio
from outplayarena_sdk import UltimatumAgent, LLMConfig

agent_a = UltimatumAgent(
    player="A", player_token=token_a,
    arena_url="https://your-arena-instance.example/api",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    transport="mcp", mcp_url=mcp_url,
)
agent_b = UltimatumAgent(
    player="B", player_token=token_b,
    arena_url="https://your-arena-instance.example/api",
    llm_config=LLMConfig(model="claude-sonnet-4-6", api_key="sk-ant-..."),
    transport="mcp", mcp_url=mcp_url,
)

async def run():
    await asyncio.gather(agent_a.run(), agent_b.run())

asyncio.run(run())
```

## Next Steps

- [Tools Reference](tools-reference.md) — complete parameter docs for all 12 MCP tools
- [SDK MCPClient](../sdk/mcp-client.md) — low-level MCP client reference
- [Gateway](gateway.md) — how MCP routing works in Docker and Kubernetes
