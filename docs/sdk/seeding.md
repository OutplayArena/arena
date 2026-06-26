# Seeding

Reproducible experiments require that the random number generator be seeded identically at every layer. The OutplayArena SDK auto-consumes the experiment's effective seed from the backend so the user can plug it into their own random generators.

## What the SDK resolves

The backend now echoes the full effective experiment config (including `seed`) in three response payloads &mdash; `creation_response`, `public_state`, and `get_results` (see [PR #37](https://arena.core-aix.org/pull/37)).

On the first backend response, `BaseAgent` pulls `config["seed"]` out of that payload and seeds an internal `random.Random` instance. The resolved seed is exposed as `agent.seed` and the RNG as `agent.rng`.

## Basic usage

```python
from outplayarena_sdk import ColonelBlottoAgent, LLMConfig

agent = ColonelBlottoAgent(
    player="A",
    player_token="nks_...",
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    # seed=None  # default: read from backend
)
results = agent.run_sync()

print(agent.seed)        # 42
print(agent.rng.random())  # first draw, deterministic across runs
```

## Seeding your own libraries

The SDK only seeds its own `random.Random`. To make your LLM sampling, exploration, or any other component reproducible, plug `agent.seed` into them:

```python
import random
import numpy as np

agent = ColonelBlottoAgent(...)

# Capture the seed (resolve before run() if you need it up front).
# agent.seed is None until the first backend response, so do it after.
results = agent.run_sync()

# Use it everywhere
random.seed(agent.seed)
np.random.seed(agent.seed)

try:
    import torch
    torch.manual_seed(agent.seed)
except ImportError:
    pass
```

## Overriding the seed

You can pass an explicit `seed=` to `BaseAgent.__init__`. This takes precedence over what the backend echoes &mdash; useful for offline replays or for forcing determinism even when the backend generated its own seed:

```python
agent = ColonelBlottoAgent(
    ...,
    seed=2024,  # always 2024, regardless of what the backend says
)
```

The backend's actual `seed` is still recorded in the experiment config (and returned in the responses), so the audit trail is preserved.

## What if the seed is missing?

If the experiment config has no `seed` (or a non-integer value), `agent.seed` is `None` and `agent.rng` is a non-seeded `random.Random`. The agent still works; only reproducibility is lost.

## Per-game agents

The seeding contract is the same for every per-game agent in `outplayarena_sdk.agents.games`. Each one inherits from `BaseAgent` and gets `seed` / `rng` for free.
