# REST vs MCP transport

`BaseAgent` accepts both `arena_url` (REST) and `mcp_url` (streamable-http). It picks MCP when both are available; otherwise it falls back to REST. This guide explains when to use which.

## What each transport does

| Transport | Endpoint | Latency | Stateful? | Best for |
| --- | --- | --- | --- | --- |
| REST | `/api/...` | low | no | scripts, batch experiments, anything where the SDK does the polling |
| MCP | `/mcp` (streamable-http) | low | session-per-agent | interactive UIs, real-time control, any case where you want to keep a long-lived session |

Both transports hit the same backend logic; the difference is the wire protocol.

## Choosing at runtime

```python
# REST only (default for new code)
agent = ColonelBlottoAgent(
    player="A", player_token="nks_...", arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    use_mcp=False,  # be explicit
)

# MCP preferred, with REST fallback
agent = ColonelBlottoAgent(
    player="A", player_token="nks_...", arena_url="http://127.0.0.1:8000/api",
    mcp_url="http://127.0.0.1:8000/mcp",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    use_mcp=True,  # default
)
```

When `mcp_url` is set and `use_mcp=True`, the agent tries to connect to MCP at construction time. If the connection fails, it falls back to REST transparently (with a warning if `verbose=True`).

## When to use REST

- **Batch experiments** &mdash; each `quick_play` / `run()` call is independent.
- **One-off scripts** &mdash; simple, no need for a long-lived MCP session.
- **CI** &mdash; the REST endpoints are more stable and easier to mock.

## When to use MCP

- **Real-time interactive UIs** &mdash; the MCP session keeps the connection warm.
- **When the backend exposes MCP-specific tools** &mdash; `get_agent_manifest`, `get_game_skill`, etc. are designed for MCP clients.
- **Long-lived agents** &mdash; if your agent stays connected for many turns, MCP avoids re-establishing the connection on each request.

## Forcing a choice

If you want to be sure, set `use_mcp=False` to force REST even when `mcp_url` is provided:

```python
agent = ColonelBlottoAgent(
    ...,
    mcp_url="http://localhost:8000/mcp",   # even if you have it
    use_mcp=False,                        # don't actually use it
)
```

## Inspecting the choice

After construction, `agent.transport` reports which one is in use:

```python
agent = ColonelBlottoAgent(...)
print(agent.transport)  # "mcp" or "rest"
```

## How the transport is selected

```python
class BaseAgent:
    async def _ensure_ready(self) -> None:
        if self._transport is not None:
            return
        rest = ArenaClient(self.arena_url)
        mcp_client: MCPClient | None = None
        if self.use_mcp and self.mcp_url:
            try:
                mcp_client = MCPClient(self.mcp_url, self.token)
                mcp_client.connect()
                self._mcp_connected = True
            except Exception as exc:
                if self.verbose:
                    print(f"[agent] MCP connect failed ({exc!r}); falling back to REST")
                mcp_client = None
        self._mcp_client = mcp_client
        self._transport = AsyncBackend(rest, mcp_client, player_id=self.player)
```

If MCP connect fails (server down, auth issue, etc.), the agent transparently falls back to REST. The agent loop doesn't care which one is serving the calls &mdash; the same `AsyncBackend` interface works either way.

## Direct access

If you need to talk to the transport directly (e.g. for a custom agent loop), `agent._transport` is an `AsyncBackend`:

```python
state = await agent._transport.get_state()
obs = await agent._transport.get_observation("neutral")
```

For most use cases, the public `BaseAgent` API is enough.

## See also

- [Transport](../transport.md) &mdash; the `AsyncBackend` reference.
- [ArenaClient](../arena-client.md) &mdash; the synchronous REST client.
- [MCPClient](../mcp-client.md) &mdash; the synchronous MCP client.
