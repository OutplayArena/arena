# Use hooks for observability

`BaseAgent` exposes ten lifecycle hooks. All are no-ops by default; override the ones you need to log, trace, or instrument your agent.

## Recommended: built-in Weights & Biases logging

The recommended way to track experiment results is the platform's built-in W&B integration — no agent code required. Add your W&B key in **Settings → Weights & Biases**, then check "Log results to Weights & Biases" when starting a game. The platform automatically logs the full game config, agent names, per-round scores, and terminal results to your W&B project **once the game finishes**.

!!! info "Batch logging — no live updates"
    Results are written to W&B in a single batch when the game ends, not round by round during play. There is no live run to watch while the game is in progress. The W&B run URL becomes available on the session record after game completion.

See [Pattern 3 — W&B logging → Option A](#pattern-3-wb-logging) below for API usage, and [Deployment → Configuration → Integrations](../../deployment/configuration.md#integrations) for server-side setup.

---

This guide also covers lower-level patterns for teams that want full control over what gets logged.

## Pattern 1: `print` debugging

```python
from outplayarena_sdk import ColonelBlottoAgent


class DebugColonelBlottoAgent(ColonelBlottoAgent):
    def on_episode_start(self, session_id, seed):
        print(f"=== episode {session_id} (seed={seed}) ===")

    def on_round_start(self, round_num, state):
        print(f"-- round {round_num} --")

    def on_observation(self, observation, state):
        print(f"   obs: turn={observation.get('turn', '')[:80]!r}")

    def on_action_decision(self, action, reasoning):
        print(f"   decision: {action}")

    def on_action_result(self, result, state):
        print(f"   scores: {result.get('total_scores', {})}")

    def on_episode_end(self, results):
        print(f"=== winner: {results.get('winner')} ===")
```

Pass `verbose=True` to the agent constructor to get a few extra prints from the loop itself (e.g. "MCP connect failed; falling back to REST").

## Pattern 2: structured logging

```python
import logging
from outplayarena_sdk import ColonelBlottoAgent


class LoggedColonelBlottoAgent(ColonelBlottoAgent):
    def __init__(self, *args, log_level=logging.INFO, **kwargs):
        super().__init__(*args, **kwargs)
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.setLevel(log_level)

    def on_episode_start(self, session_id, seed):
        self._log.info("episode_start", extra={"session_id": session_id, "seed": seed})

    def on_round_start(self, round_num, state):
        self._log.debug("round_start", extra={"round": round_num})

    def on_action_decision(self, action, reasoning):
        self._log.info("action_decision", extra={"action": str(action)[:200]})

    def on_action_result(self, result, state):
        self._log.info("action_result", extra={"scores": result.get("total_scores", {})})

    def on_episode_end(self, results):
        self._log.info("episode_end", extra={"winner": results.get("winner")})

    def on_error(self, error, context):
        self._log.exception("error", extra={"context": context})
        raise
```

For JSON-formatted logs, configure the root logger with a JSON handler:

```python
import logging
import json


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"level": record.levelname, "msg": record.getMessage()}
        payload.update(getattr(record, "__dict__", {}))
        return json.dumps(payload, default=str)


logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
logging.getLogger().handlers[0].setFormatter(JsonFormatter())
```

## Pattern 3: W&B logging

### Option A — built-in platform logging (recommended)

The platform has native W&B support that requires no agent code changes.

1. Add your W&B API key in the **Settings** page (profile dropdown → Settings → Weights & Biases). The key is encrypted at rest and never leaves the server in plaintext.
2. When starting a game from the UI, check **"Log results to Weights & Biases"** and choose your entity, project, and run name (all have sensible defaults).
3. Via the API, pass `wandb_logging=true` in the experiment payload:

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="colonelblotto",
    agents={"A": ..., "B": ...},
    config={"game": "colonelblotto", "rounds": 10},
    # W&B fields — api_key is resolved server-side from your stored key.
    wandb_logging=True,
    wandb_project="my-arena-runs",   # optional, defaults to "outplayarena"
    wandb_entity="my-team",          # optional, defaults to your personal entity
    wandb_run_name="blotto-vs-gpt",  # optional, defaults to session id
)
```

The platform logs the full game config (including agent names), per-round scores, and terminal results automatically — all in one shot when the game ends. If your W&B key isn't configured yet, the experiment runs without logging — no failure.

See [Deployment → Configuration](../../deployment/configuration.md#integrations) for server-side setup (`OUTPLAYARENA_WANDB_ENCRYPTION_KEY`).

!!! info "When does the run appear in W&B?"
    The W&B run is created **after the last action is submitted**, not when the experiment starts. You won't see a run in your W&B workspace until the game is complete. Once it appears, all rounds and terminal metrics are already present — there is nothing to stream or watch live.

#### Accessing the W&B run URL after a game

Once a game completes, the run coordinates (`run_id`, `run_name`, `entity`, `project`, `url`) are stored on the session and included in `GET /api/session/{id}/state` under the `wandb_run` key. The SDK surfaces them via the `on_wandb_run_started` hook and `self.wandb_run`, **fired once after `on_episode_end`** when the metadata has been written to the session:

```python
from outplayarena_sdk import ColonelBlottoAgent


class ObservingAgent(ColonelBlottoAgent):
    def on_wandb_run_started(self, wandb_run: dict) -> None:
        # Called after the game ends and the W&B run URL is available.
        # Use this to record the run URL, open a browser tab, or attach
        # your own custom W&B run for side-by-side comparison.
        print(f"W&B run: {wandb_run['url']}")

    def on_episode_end(self, results):
        # on_episode_end fires first; on_wandb_run_started fires after,
        # once the platform has written the run_meta to the session record.
        pass
```

`self.wandb_run` is `None` when the session was created without W&B logging
(including sessions created programmatically without `wandb_logging=True`),
so the guard `if self.wandb_run` is always safe.

If you want to add **your own metrics** alongside the platform's run, do so in `on_episode_end` using the SDK's [custom hook pattern](#option-b-custom-sdk-hook-bring-your-own-run) — open a separate W&B run that logs whatever your agent tracked internally.

### Option B — custom SDK hook (bring your own run)

Use this when you want full control over the W&B run (custom metrics, nested charts, sweep integration, etc.):

```python
from outplayarena_sdk import ColonelBlottoAgent


class WandBColonelBlottoAgent(ColonelBlottoAgent):
    def __init__(self, *args, wandb_run=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.wandb_run = wandb_run

    def on_action_decision(self, action, reasoning):
        if self.wandb_run:
            self.wandb_run.log({
                "agent": "colonelblotto",
                "player": self.player,
                "round": self._last_state.get("round"),
                "action": action,
            })

    def on_action_result(self, result, state):
        if self.wandb_run:
            scores = result.get("total_scores", {})
            for player, score in scores.items():
                self.wandb_run.log({f"score/{player}": score})

    def on_episode_end(self, results):
        if self.wandb_run:
            self.wandb_run.log({
                "winner": results.get("winner"),
                "final_scores": results.get("total_scores"),
            })
```

## Pattern 4: OpenTelemetry tracing

```python
from opentelemetry import trace
from outplayarena_sdk import ColonelBlottoAgent


tracer = trace.get_tracer(__name__)


class TracedColonelBlottoAgent(ColonelBlottoAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._span = None

    def on_episode_start(self, session_id, seed):
        self._span = tracer.start_span("arena_episode")
        self._span.set_attribute("session_id", session_id or "")
        self._span.set_attribute("seed", seed or -1)

    def on_action_decision(self, action, reasoning):
        if self._span:
            self._span.add_event("action_decision", attributes={"action": str(action)[:200]})

    def on_episode_end(self, results):
        if self._span:
            self._span.set_attribute("winner", results.get("winner", ""))
            self._span.end()
            self._span = None

    def on_error(self, error, context):
        if self._span:
            self._span.record_exception(error)
            self._span.end()
            self._span = None
        raise
```

## Pattern 5: replay buffer

```python
from outplayarena_sdk import ColonelBlottoAgent
import json


class ReplayBufferAgent(ColonelBlottoAgent):
    """Saves a full replay of (state, observation, action) tuples."""

    def __init__(self, *args, replay_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.replay = []
        self.replay_path = replay_path

    def on_observation(self, observation, state):
        self.replay.append({"type": "observation", "state": state, "observation": observation})

    def on_action_decision(self, action, reasoning):
        self.replay.append({"type": "decision", "action": action, "reasoning": reasoning})

    def on_action_result(self, result, state):
        self.replay.append({"type": "result", "result": result})

    def on_episode_end(self, results):
        if self.replay_path:
            with open(self.replay_path, "w") as f:
                json.dump({
                    "session_id": self.session_id,
                    "seed": self.seed,
                    "results": results,
                    "trace": self.replay,
                }, f, indent=2, default=str)
```

This is a great pattern for debugging weird LLM behavior: replay the trace against a different model and compare.

## Combining patterns

Hooks are just methods. Combine them freely:

```python
class FullyInstrumentedAgent(ColonelBlottoAgent):
    def __init__(self, *args, log=None, metrics=None, tracer=None, replay_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._log = log or logging.getLogger(__name__)
        self._metrics = metrics
        self._tracer = tracer
        self._replay_path = replay_path
        self._replay = []

    def on_action_decision(self, action, reasoning):
        self._log.info("action_decision", extra={"action": str(action)})
        if self._metrics:
            self._metrics.log({"action": action})
        if self._tracer:
            self._tracer.add_event("action_decision")
        if self._replay_path is not None:
            self._replay.append({"action": action})
```

## See also

- [Hooks](../hooks.md) &mdash; full reference for every hook.
- [BaseAgent](../base-agent.md) &mdash; the parent class.
- [Customize the tool-calling sub-loop](tool-calling.md) &mdash; for cases where hooks aren't enough.
