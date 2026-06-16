# Reasoning Control

Control how LLM agents reason before acting. The `ReasoningModerator` adapts to different model capabilities.

## Overview

Different LLM models have different reasoning capabilities and control mechanisms:

- **OpenAI o-series** (o1, o3, o4-mini): Support `reasoning_effort` API parameter
- **Anthropic Claude**: Support `thinking` toggle and `budget_tokens`
- **DeepSeek**: Support `thinking` via `enable_thinking` parameter
- **Standard models** (GPT-4, Claude 3): No dedicated reasoning control

`ReasoningModerator` provides a unified interface that adapts to each model's capabilities.

## Reasoning Effort Levels

```python
from nash_arena_sdk import ReasoningEffort

ReasoningEffort.NONE    # No reasoning control
ReasoningEffort.LOW     # Minimal reasoning budget
ReasoningEffort.MEDIUM  # Moderate reasoning budget
ReasoningEffort.HIGH    # Maximum reasoning budget
```

## Basic Usage

```python
from nash_arena_sdk import ReasoningModerator, ReasoningEffort

# Create a moderator for a specific model
moderator = ReasoningModerator(
    model_id="deepseek-v3",
    effort=ReasoningEffort.HIGH,
    prompt_hint=True,  # Add reasoning hints to prompts
)

# Prepare request body with model-specific parameters
body = moderator.prepare_request_body(
    messages=[{"role": "user", "content": "What's your move?"}],
    temperature=0.7,
)
# For DeepSeek: {"enable_thinking": True, "thinking_budget": 4096, ...}
# For OpenAI o3: {"reasoning_effort": "high", ...}

# Extract response text (handles model-specific response formats)
text, reasoning = moderator.extract_response_text(response_data)
```

## Model Profiles

The SDK includes profiles for 30+ models:

```python
from nash_arena_sdk import MODEL_PROFILES, get_model_profile

# Get profile for a specific model
profile = get_model_profile("deepseek-v3")
print(profile.provider)              # "deepseek"
print(profile.preferred_strategy)    # ReasoningStrategy.API_CONTROL
print(profile.supports_thinking_toggle)  # True

# List all profiles
for model_id, profile in MODEL_PROFILES.items():
    print(f"{model_id}: {profile.provider}")
```

## Reasoning Strategies

Models use different strategies for reasoning control:

| Strategy | Description | Models |
|----------|-------------|--------|
| `API_CONTROL` | Dedicated API parameter for reasoning budget | OpenAI o-series, DeepSeek, GLM |
| `BUDGET_PROMPT` | Prompt-based reasoning constraints | Claude (via system prompt) |
| `STUBBORN` | No reasoning control available | Standard GPT-4, Claude 3 |

## Integration with LLMAgent

Reasoning control is built into `LLMAgent`:

```python
from nash_arena_sdk import LLMAgent, LLMConfig, ReasoningEffort

config = LLMConfig(
    model="deepseek-v3",
    api_key="sk-...",
    reasoning_effort=ReasoningEffort.HIGH,  # Enable reasoning control
)

agent = LLMAgent(
    player="A",
    player_token="nks_...",
    arena_url="http://127.0.0.1:8000/api",
    llm_config=config,
)

# The agent automatically applies reasoning control
obs = await agent.get_observation()
action = agent.act(obs, state)  # Uses ReasoningModerator internally
```

## Token Limits

The moderator enforces token limits based on effort level:

```python
limits = moderator.get_limits()
# Returns:
# {
#     "max_tokens": 4096,
#     "thinking_budget": 2048,  # If applicable
#     "timeout_seconds": 120,
# }
```

## System Prompt Augmentation

When `prompt_hint=True`, the moderator augments system prompts with reasoning guidance:

```python
base_prompt = "You are playing a game..."
augmented = moderator.build_system_prompt(base_prompt)
# Adds reasoning hints based on model capabilities
```

## API Reference

::: nash_arena_sdk.reasoning.ReasoningModerator
    options:
      members:
        - __init__
        - from_config
        - strategy
        - effort
        - get_api_params
        - get_limits
        - build_system_prompt
        - prepare_request_body
        - extract_response_text

::: nash_arena_sdk.reasoning.ReasoningEffort
    options:
      show_root_heading: true

::: nash_arena_sdk.reasoning.ReasoningStrategy
    options:
      show_root_heading: true
