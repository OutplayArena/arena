# Customize a per-game agent

The 10 built-in per-game agents in `outplaylabs_arena_sdk.agents.games` are the lowest-friction starting point. This guide shows how to customize them: override the action format hint, override the parser, or add custom communication.

## Override the action format hint

The hint is the most important thing the LLM sees about your game. Make it specific:

```python
from outplaylabs_arena_sdk import ColonelBlottoAgent, LLMConfig


class ConservativeColonelBlottoAgent(ColonelBlottoAgent):
    """Avoid extreme allocations: prefer a balanced spread."""

    def action_format_hint(self) -> str:
        state = self._last_state or {}
        n = len(state.get("battlefields", []))
        budget = state.get("budgets", {}).get(self.player, 0)
        if not n or not budget:
            return super().action_format_hint()
        return (
            f"a Python list of {n} non-negative integers summing to {budget}. "
            f"Prefer balanced values: at most {budget // 2} on any one field. "
            f"Example: [{budget // n}] * {n}."
        )
```

The hint is read on every turn (because `action_format_hint` is called each time the LLM is invoked), so you can use the current state to make it dynamic.

## Override the parser

If you want stricter validation or a different fallback than the default, override `parse_action`:

```python
from outplaylabs_arena_sdk import ColonelBlottoAgent
from outplaylabs_arena_sdk.parsers import parse_allocation


class StrictColonelBlottoAgent(ColonelBlottoAgent):
    """Reject allocations that put more than 60% on any one field."""

    def parse_action(self, raw_text, state):
        battlefields = state.get("battlefields", [])
        budgets = state.get("budgets", {})
        n = len(battlefields)
        total = budgets.get(self.player, 0)
        if not n or not total:
            return []
        cap = int(total * 0.6)
        allocation = parse_allocation(raw_text, n, total)
        # Clamp any field above the cap.
        return [min(a, cap) for a in allocation]
```

If the LLM's response is unparseable, `parse_allocation` returns a balanced fallback. The clamping on top of that enforces the 60% rule.

## Add custom communication

```python
class ChattyColonelBlottoAgent(ColonelBlottoAgent):
    def maybe_communicate(self, state):
        # Send a blurb on the last round.
        if state.get("round") == state.get("round_total"):
            return "Good game. Looking forward to the results."
        # Send a strategic hint on the first round.
        if state.get("round") == 1:
            return "Let's both play balanced. Should be more interesting."
        return None
```

When this returns a non-`None` string, the agent sends it via `send_message` and fires `on_message_received`.

## Override the LLM call

If you need full control over the LLM request, override `_call_llm_with_tools` and/or `_call_llm_plain`:

```python
import json


class JSONConstrainedColonelBlottoAgent(ColonelBlottoAgent):
    """Force the LLM to respond with structured JSON."""

    def _call_llm_with_tools(self, messages, tools):
        # Replace the system prompt with a strict JSON instruction.
        messages = [
            {
                "role": "system",
                "content": "Respond ONLY with JSON: {\"allocation\": [int, int, ...]}",
            },
            *messages[1:],
        ]
        # Use json_mode in the kwargs.
        return self._openai.chat.completions.create(
            model=self.llm_config.model,
            messages=messages,
            temperature=0,
            max_tokens=128,
            response_format={"type": "json_object"},
        )
```

This is the escape hatch for providers that don't support `tools=` or for workflows that need tighter JSON-output guarantees.

## Add post-decision rules

The `on_action_decision` hook is the right place for game-specific rules you want to enforce after the LLM commits:

```python
class ConservativeColonelBlottoAgent(ColonelBlottoAgent):
    def on_action_decision(self, action, reasoning):
        # Re-validate and possibly override.
        if isinstance(action, list):
            battlefields = (self._last_state or {}).get("battlefields", [])
            budgets = (self._last_state or {}).get("budgets", {})
            total = budgets.get(self.player, 0)
            if total and len(action) == len(battlefields):
                cap = int(total * 0.6)
                if any(a > cap for a in action):
                    print(f"[{self.player}] overriding extreme allocation: {action}")
                    # Note: this only logs; mutating `action` after this
                    # point won't reach the backend. To actually change
                    # the action, override `parse_action` instead.
        super().on_action_decision(action, reasoning)
```

To actually change the action that gets submitted, override `parse_action` &mdash; `on_action_decision` is for observation, not mutation.

## See also

- [Per-game agents](../per-game-agents.md) &mdash; the full list of built-in subclasses.
- [Parsers](../parsers.md) &mdash; the parsers you can reuse in your override.
- [Hooks](../hooks.md) &mdash; the full lifecycle hook reference.
- [BaseAgent](../base-agent.md) &mdash; the parent class.
