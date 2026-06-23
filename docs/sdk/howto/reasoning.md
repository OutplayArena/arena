# Customize reasoning control

`LLMConfig.reasoning_effort` controls how much "thinking" budget the LLM gets before producing a final answer. This guide shows how to pick the right level and how to customize the behavior per model.

## The four effort levels

| Level | Effect |
| --- | --- |
| `none` | No reasoning control. The model responds immediately. |
| `low` | Minimal reasoning. The LLM gets a short budget. |
| `medium` | Moderate reasoning. |
| `high` | Maximum reasoning. Long budget, long timeout. |

Set the level on `LLMConfig`:

```python
from outplaylabs_arena_sdk import ColonelBlottoAgent, LLMConfig, ReasoningEffort

agent = ColonelBlottoAgent(
    ...,
    llm_config=LLMConfig(
        model="gpt-5",
        api_key="sk-...",
        reasoning_effort=ReasoningEffort.HIGH,
    ),
)
```

## What changes per effort

`BaseAgent` passes the effort to `ReasoningModerator`, which:

1. Picks a `max_tokens` for the response (512 / 1024 / 4096 / 16384).
2. Computes a per-call timeout based on the model's `baseline_response_time`.
3. Adds a budget hint to the LLM system prompt (e.g. "You have a brief moment. Think in at most 2 sentences...").
4. Sets the appropriate API parameter (`reasoning_effort`, `thinking`, `enable_thinking`, or nothing) based on the model's profile.

## Per-model defaults

`ReasoningModerator` looks up the model in `MODEL_PROFILES`. Each entry knows which reasoning control mechanisms the model supports:

| Provider | Default strategy | Mechanism |
| --- | --- | --- |
| OpenAI o-series | `API_CONTROL` | `reasoning_effort` |
| OpenAI standard (gpt-4o, gpt-4.1) | `BUDGET_PROMPT` | prompt hint |
| Anthropic Claude | `API_CONTROL` | `thinking` |
| Google Gemini | `API_CONTROL` | `thinking` |
| DeepSeek | `API_CONTROL` | `thinking` |
| Qwen | `API_CONTROL` | `enable_thinking` |
| GLM, Mistral, Llama, Cohere | `BUDGET_PROMPT` | prompt hint |
| MiMo (Xiaomi) | `STUBBORN` | (none; the model ignores the hint) |

If the model isn't in `MODEL_PROFILES`, the moderator falls back to `BUDGET_PROMPT` (always responds to prompt hints).

## Inspect the moderator

```python
from outplaylabs_arena_sdk import ReasoningModerator, ReasoningEffort

mod = ReasoningModerator("gpt-5", effort=ReasoningEffort.HIGH)
print(mod.profile.provider)         # "openai"
print(mod.get_api_params())          # {"reasoning_effort": "high"}
print(mod.get_limits())              # {"max_tokens": 16384, "timeout": 70.0}
print(mod.build_system_prompt("You are playing."))  # "You are playing. You have time to..."
```

## Override per-agent

To use a different effort per agent in a multi-agent run:

```python
agents = {
    "A": ColonelBlottoAgent(
        player="A", player_token=tokens["A"], arena_url=arena_url,
        llm_config=LLMConfig(model="gpt-5", api_key="sk-...", reasoning_effort=ReasoningEffort.HIGH),
    ),
    "B": ColonelBlottoAgent(
        player="B", player_token=tokens["B"], arena_url=arena_url,
        llm_config=LLMConfig(model="claude-3-opus", api_key="sk-ant-...", reasoning_effort=ReasoningEffort.LOW),
    ),
}
```

## Override the API parameter

If the model's profile is wrong about which API parameter to use, you can override:

```python
class CustomReasoningAgent(ColonelBlottoAgent):
    def _call_llm_with_tools(self, messages, tools):
        kwargs = {
            "model": self.llm_config.model,
            "messages": messages,
            "temperature": self.llm_config.temperature,
            "max_tokens": self.llm_config.max_tokens,
            "tools": tools,
        }
        # Force a specific parameter regardless of profile.
        if self.llm_config.reasoning_effort != "none":
            kwargs["extra_body"] = {"thinking": {"type": "enabled", "budget": 8192}}
        return self._openai.chat.completions.create(**kwargs)
```

## Add a new model profile

If the model isn't in `MODEL_PROFILES`, the moderator falls back to a default `BUDGET_PROMPT` strategy. You can register a custom profile:

```python
from outplaylabs_arena_sdk.reasoning import (
    ModelProfile, ReasoningStrategy, MODEL_PROFILES,
)


MODEL_PROFILES["my-new-model"] = ModelProfile(
    model_id="my-new-model",
    provider="my-provider",
    supports_thinking_toggle=True,
    supports_reasoning_effort=False,
    supports_enable_thinking=False,
    baseline_response_time=5.0,
    preferred_strategy=ReasoningStrategy.API_CONTROL,
)
```

After this registration, `ReasoningModerator("my-new-model", effort=ReasoningEffort.LOW)` will use the `thinking` parameter.

## See also

- [Reasoning control](../reasoning.md) &mdash; the full reference.
- [BaseAgent](../base-agent.md) &mdash; the parent class.
- [Customize the tool-calling sub-loop](tool-calling.md) &mdash; for advanced LLM integrations.
