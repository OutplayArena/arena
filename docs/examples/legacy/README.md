# Legacy examples

These scripts use the pre-`BaseAgent` SDK API (`MCPAgent`, hand-rolled game
loops, custom OpenAI calls). They are kept here for reference and to avoid
breaking CI that depends on them, but **new code should use `BaseAgent` or
`quick_play`** from the modern SDK.

For current examples, see:

- [`agent-sdk/README.md`](../../../agent-sdk/README.md) &mdash; quick start with `BaseAgent` and `quick_play`.
- [`docs/agents.md`](../../agents.md) &mdash; guide to building custom agents.
- [`docs/seeding.md`](../../seeding.md) &mdash; seeding guide.

## Why these are "legacy"

Before the `BaseAgent` rework, every script had to:

1. Open a `MCPClient` / `ArenaClient`.
2. Hand-roll a polling loop.
3. Call OpenAI with custom function-calling logic.
4. Parse the LLM's text output into a game-specific action.
5. Submit and repeat.

That logic is now in `BaseAgent` and the per-game subclasses
(`ColonelBlottoAgent`, `UltimatumAgent`, ...). The legacy scripts in this
folder are useful for studying the lower-level mechanics, but they are
duplicated effort compared to the new API.
