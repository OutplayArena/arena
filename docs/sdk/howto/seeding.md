# Make experiments reproducible

The SDK exposes the experiment's effective `seed` via `agent.seed` and provides a seeded `random.Random` via `agent.rng`. This guide shows how to use them everywhere in your experiment to make results reproducible across runs.

## The contract

- The backend now echoes the effective experiment config (including `seed`) in three responses: `creation_response`, `public_state`, and `get_results` (see [PR #37](https://github.com/Outplaylabs/arena/pull/37)).
- `BaseAgent` reads `config["seed"]` from the first backend response it gets.
- `agent.seed` is the resolved seed (or your override if you passed `seed=` to the constructor).
- `agent.rng` is a `random.Random` instance seeded with `agent.seed`.

## The basic pattern

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

# Now seed your other libraries
import random
import numpy as np

random.seed(agent.seed)
np.random.seed(agent.seed)

try:
    import torch
    torch.manual_seed(agent.seed)
except ImportError:
    pass
```

Note: `agent.seed` is only set after the first backend response (i.e. during `run()`). If you need the seed before `run()`, either pass an explicit `seed=` or fetch the state once and then start your random sources.

## Overriding the seed

Pass an explicit `seed=` to `BaseAgent.__init__` to force a specific seed:

```python
agent = ColonelBlottoAgent(
    ...,
    seed=2024,  # always 2024, regardless of what the backend says
)
```

The backend's actual seed is still in the experiment config and in the responses, so the audit trail is preserved.

## Seeding before `run()` (advanced)

If you need `agent.seed` to be available before the loop starts, fetch the state once manually:

```python
import httpx
from outplayarena_sdk import ColonelBlottoAgent, LLMConfig, ArenaClient

# Create the experiment yourself to know the seed up front.
rest = ArenaClient("http://127.0.0.1:8000/api")
created = rest.create_experiment(
    {"game": "colonelblotto", "variant": "classic", "players": 2,
     "budget": [50, 50], "battlefields": [{"id": "A", "value": 1.0},
     {"id": "B", "value": 1.0}], "rounds": 10, "seed": 42},
    api_key="nk_...",
)
seed = created["config"]["seed"]  # 42

# Now seed everything
import random
import numpy as np
random.seed(seed)
np.random.seed(seed)

# Then build the agent; it will resolve to the same seed
agent = ColonelBlottoAgent(
    player="A",
    player_token=created["player_tokens"]["A"],
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    seed=seed,
)
results = agent.run_sync()
```

## Seeding your own random sources from `agent.rng`

The cleanest pattern is to copy `agent.rng` rather than re-seeding global state:

```python
my_rng = random.Random(agent.seed)        # independent copy
my_rng = agent.rng                        # alias (draws affect both)
```

If you use `agent.rng` directly, be aware that `BaseAgent` and the parsers also draw from it, so the stream is shared.

## Per-turn randomness in hooks

If a hook needs random numbers (e.g. for an epsilon-greedy exploration strategy), use `agent.rng`:

```python
class EpsilonGreedyAgent(ColonelBlottoAgent):
    def __init__(self, *args, epsilon=0.1, **kwargs):
        super().__init__(*args, **kwargs)
        self.epsilon = epsilon

    def on_round_start(self, round_num, state):
        if self.rng.random() < self.epsilon:
            self._explore = True
        else:
            self._explore = False

    def on_action_decision(self, action, reasoning):
        if self._explore:
            print(f"[{self.player}] round {round_num}: exploring")
```

Because `self.rng` is seeded, this exploration is reproducible.

## When the seed is missing

If the experiment config has no `seed` (or a non-integer value), `agent.seed` is `None` and `agent.rng` is a non-seeded `random.Random`. The agent still works; only reproducibility is lost.

You can detect this and warn:

```python
results = agent.run_sync()
if agent.seed is None:
    print(f"WARNING: no seed available; results are not reproducible (session_id={agent.session_id})")
```

## See also

- [Seeding](../seeding.md) &mdash; the full reference.
- [BaseAgent](../base-agent.md) &mdash; how `agent.seed` and `agent.rng` are wired in.
