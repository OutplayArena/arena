# Lifecycle hooks

`BaseAgent` emits ten lifecycle hooks during each `run()` call. All are no-ops by default; override the ones you need.

## Reference

| Hook | When | Signature |
| --- | --- | --- |
| `on_episode_start` | once, before the loop | `(session_id: str \| None, seed: int \| None)` |
| `on_round_start` | top of every poll iteration | `(round_num: int, state: dict)` |
| `on_observation` | after `get_observation` | `(observation: dict, state: dict)` |
| `on_tool_call` | after each backend tool the LLM invokes | `(name: str, arguments: dict, result: Any)` |
| `on_action_decision` | once per turn, after the LLM commits | `(action: Any, reasoning: str)` |
| `on_action_result` | after `submit_action` | `(result: dict, state: dict)` |
| `on_message_received` | when `maybe_communicate` produced a message | `(message: dict)` |
| `on_round_end` | bottom of every poll iteration | `(round_num: int, state: dict)` |
| `on_episode_end` | once, after the game completes | `(results: dict)` |
| `on_error` | any exception in the loop | `(error: Exception, context: dict)` &rarr; re-raises by default |

## Execution order

For a typical turn where the agent is in `awaiting`:

```
on_episode_start                              (once, before the loop)
└─ while not terminal:
    on_round_start                             (top of iteration)
    ├─ on_observation
    ├─ on_tool_call ×N                         (LLM uses backend tools)
    ├─ on_action_decision
    ├─ on_action_result
    └─ on_message_received                     (if maybe_communicate returns a string)
    on_round_end                               (bottom of iteration)
on_episode_end                                (once, after the loop)
```

When the agent is **not** in `awaiting`, only `on_round_start` and `on_round_end` fire for that iteration &mdash; the inner hooks are skipped.

## What each hook is for

### `on_episode_start`

Called once, right after the agent connects and resolves the config. Use it to:

- Open a log file or initialize a metrics client.
- Reset per-episode state (round counter, history buffer).
- Print a banner.

```python
def on_episode_start(self, session_id, seed):
    print(f"=== Starting episode {session_id} (seed={seed}) ===")
    self._start = time.monotonic()
    self._decisions = []
```

### `on_round_start` / `on_round_end`

Bracketing a single poll iteration. Use `on_round_start` to log "looking at round N" and `on_round_end` to record the final state of the iteration.

```python
def on_round_start(self, round_num, state):
    self._log.info("round_start", round=round_num, phase=state.get("phase"))

def on_round_end(self, round_num, state):
    self._log.info("round_end", round=round_num, awaiting=state.get("awaiting"))
```

### `on_observation`

Called after the LLM-ready prompts are fetched. Use it to inspect or log what the LLM will see:

```python
def on_observation(self, observation, state):
    self._log.debug("observation", system=observation.get("system", "")[:120], turn=observation.get("turn", "")[:120])
```

### `on_tool_call`

Called once for each backend tool the LLM invokes during the per-turn sub-loop. Use it to log tool usage or instrument the agent:

```python
def on_tool_call(self, name, arguments, result):
    self._tool_log.append({"name": name, "args": arguments, "result_preview": str(result)[:200]})
```

`name` is one of `get_observation`, `get_game_state`, `get_mailbox`, `send_message`, or `submit_action`. The `submit_action` tool call has `"committed": True` in its result to mark it as the one that ended the sub-loop.

### `on_action_decision`

Called once per turn, after the LLM has committed to an action. The `reasoning` is the raw text the LLM produced (or the empty string if the LLM used the `submit_action` tool).

```python
def on_action_decision(self, action, reasoning):
    self._decisions.append({
        "round": self._last_state.get("round"),
        "action": action,
        "reasoning": reasoning,
    })
```

### `on_action_result`

Called after `submit_action` returns. The result is the updated public state from the backend:

```python
def on_action_result(self, result, state):
    round_scores = result.get("total_scores", {})
    if self.metrics:
        self.metrics.log({"round_scores": round_scores})
```

### `on_message_received`

Called only if `maybe_communicate` returned a string and the mailbox send succeeded:

```python
def on_message_received(self, message):
    self._log.info("sent_message", recipient=message.get("recipient"), length=len(message.get("content", "")))
```

### `on_episode_end`

Called once, after the game reaches a terminal state. Use it to flush logs, close metrics clients, or print a summary:

```python
def on_episode_end(self, results):
    elapsed = time.monotonic() - self._start
    self._log.info("episode_end", winner=results.get("winner"), elapsed=elapsed)
    self.metrics.flush()
```

### `on_error`

Called when any exception propagates out of the loop. The default is to re-raise (so the error surfaces to the caller). Override to:

- Log and re-raise (most common).
- Log and swallow (e.g. for one bad turn out of many).
- Log and return a fallback action (rare; usually a sign the agent is fundamentally broken).

```python
def on_error(self, error, context):
    self._log.exception("agent_loop_error", error=str(error), context=context)
    raise
```

The `context` dict contains `{"session_id": ..., "state": self._last_state}` for debugging.

## Patterns

### Logging and metrics

```python
class InstrumentedAgent(ColonelBlottoAgent):
    def __init__(self, *args, metrics_client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = metrics_client
        self._decisions = []

    def on_action_decision(self, action, reasoning):
        self._decisions.append({
            "round": self._last_state.get("round"),
            "action": action,
        })

    def on_episode_end(self, results):
        if self.metrics:
            self.metrics.log({
                "agent": "colonelblotto",
                "decisions": self._decisions,
                "final_scores": results.get("total_scores"),
            })
```

### Custom communication

```python
class ChattyAgent(ColonelBlottoAgent):
    def maybe_communicate(self, state):
        # Send a strategic blurb on the last round.
        if state.get("round") == state.get("round_total"):
            return "Good game. Let's see the results."
        return None
```

### Resilient error handling

```python
class ResilientAgent(ColonelBlottoAgent):
    def on_error(self, error, context):
        # Log and re-raise — but mark the round as "lost" first.
        self._lost_rounds.add(context["state"].get("round"))
        raise
```

## See also

- [BaseAgent](base-agent.md) &mdash; the class these hooks belong to.
- [How-to: instrument with hooks and metrics](howto/hooks-and-metrics.md) &mdash; a complete worked example.
