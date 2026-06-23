# Transport

The `outplaylabs_arena_sdk.transport.AsyncBackend` class is the async wrapper that `BaseAgent` uses to talk to the backend. It supports both REST (via `ArenaClient`) and MCP (via `MCPClient`).

Most users do not need to interact with `AsyncBackend` directly &mdash; `BaseAgent` constructs and drives it. This page documents the class for advanced cases (custom agent loops, library integrations, testing).

## What it does

`AsyncBackend` provides a uniform async interface for the 9 backend operations an agent might perform:

| Method | REST | MCP |
| --- | --- | --- |
| `get_state()` | ✓ | ✓ |
| `get_observation(variant)` | ✓ | ✓ |
| `submit_action(allocation)` | ✓ | ✓ |
| `get_results()` | ✓ | ✓ |
| `get_mailbox()` | ✓ | ✓ |
| `send_message(content, recipient)` | ✓ | ✓ |
| `list_games()` | ✓ | &mdash; |
| `get_game_details(game)` | ✓ | &mdash; |

When both transports are configured, MCP is preferred for the methods it supports; REST is used for the rest. The selection is made per-method, not at construction.

## Construction

```python
from outplaylabs_arena_sdk import ArenaClient, MCPClient
from outplaylabs_arena_sdk.transport import AsyncBackend

rest = ArenaClient("http://127.0.0.1:8000/api")
mcp = MCPClient("http://127.0.0.1:8000/mcp", "nks_...")  # optional
mcp.connect()

backend = AsyncBackend(rest, mcp, player_id="A")
```

`player_id` is required for the methods that need it (`get_observation` and `get_mailbox` use it to scope the response to the calling player). `BaseAgent` sets this automatically; if you build an `AsyncBackend` manually, set it before calling those methods.

You can also set it after construction:

```python
backend = AsyncBackend(rest)
backend.set_player_id("A")
```

## Selecting a transport

```python
backend = AsyncBackend(rest)              # REST only
backend.transport                         # → "rest"

backend = AsyncBackend(rest, mcp)         # MCP preferred
backend.transport                         # → "mcp"
```

The selection is per-method: if MCP supports it, MCP is used; otherwise REST is used. The agent loop does not need to know which transport served a given call.

## Methods

### `get_state()`

```python
state = await backend.get_state()
# {"session_id": ..., "phase": ..., "awaiting": [...], "round": ..., "config": {...}}
```

Fetch the current public state. Available via both transports.

### `get_observation(variant="neutral")`

```python
obs = await backend.get_observation("neutral")
# {"system": "...", "turn": "..."}
```

Render the LLM-ready prompts for the current state. `variant` is one of `"neutral"`, `"gain_framed"`, `"loss_framed"`. Requires a `player_id` to be set.

### `submit_action(allocation)`

```python
result = await backend.submit_action([10, 20, 30])
# {"status": "ok", ...updated public state...}
```

Commit the action for the current round. The result is the updated public state from the backend.

### `get_results()`

```python
results = await backend.get_results()
# {"winner": "A", "total_scores": {...}, "metrics": {...}, "config": {...}}
```

Fetch the final results. Only available once the game is complete.

### `get_mailbox()`

```python
messages = await backend.get_mailbox()
# [{"id": "1", "sender": "B", "content": "...", ...}, ...]
```

Read the inbox. Requires a `player_id` to be set.

### `send_message(content, recipient="all")`

```python
result = await backend.send_message("hello", recipient="B")
# {"id": "1", "content": "hello", "recipient": "B", ...}
```

Write to the inbox.

### `list_games()` and `get_game_details(game)`

REST-only discovery methods. Not used by `BaseAgent` directly; useful for one-off setup.

## When to use `AsyncBackend` directly

| Scenario | Recommendation |
| --- | --- |
| Building a custom agent loop | Use `BaseAgent` + subclass. |
| Building a one-off script that polls without an LLM | Use `ArenaClient` (synchronous). |
| Integrating the SDK into an existing async framework | Use `AsyncBackend` directly. |
| Writing tests that mock the backend | Use `AsyncBackend` with a mocked transport. |

## Example: a custom polling loop

```python
import asyncio
from outplaylabs_arena_sdk import ArenaClient, MCPClient
from outplaylabs_arena_sdk.transport import AsyncBackend


async def poll_until_terminal(backend: AsyncBackend, player: str) -> dict:
    while True:
        state = await backend.get_state()
        if state.get("phase") == "complete":
            return await backend.get_results()
        if player in state.get("awaiting", []):
            obs = await backend.get_observation()
            print(f"[{player}] observation: {obs}")
        await asyncio.sleep(1.0)


async def main():
    rest = ArenaClient("http://127.0.0.1:8000/api")
    backend = AsyncBackend(rest, player_id="A")
    results = await poll_until_terminal(backend, "A")
    print(results)


asyncio.run(main())
```

## See also

- [BaseAgent](base-agent.md) &mdash; the high-level user of `AsyncBackend`.
- [ArenaClient](arena-client.md) &mdash; the synchronous REST client.
- [MCPClient](mcp-client.md) &mdash; the synchronous MCP client.
