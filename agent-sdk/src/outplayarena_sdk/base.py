"""Base agent for the OutplayArena SDK.

:class:`BaseAgent` is the single entry point for building autonomous agents
that play games on the platform. It owns the full lifecycle:

  1. Connect a backend transport (REST or MCP).
  2. Resolve the effective experiment config (and seed) on first contact.
  3. Drive the per-turn loop: while the game is not complete and the
     player is in ``state["awaiting"]``, fetch the observation, decide
     an action (with optional tool-calling), and submit it.
  4. Emit lifecycle hooks at every meaningful point so subclasses (and
     end users) can plug in custom logic.

Per-game knowledge lives in subclasses under :mod:`outplayarena_sdk.agents.games`.
Those override :meth:`parse_action` to convert the LLM's text output into
the game's structured action format, and :meth:`action_format_hint` to
guide the LLM. :class:`BaseAgent` itself does not know any game rules.

Example::

    from outplayarena_sdk.llm_config import LLMConfig
    from outplayarena_sdk.agents.games import ColonelBlottoAgent

    agent = ColonelBlottoAgent(
        player="A",
        player_token="nks_...",
        arena_url="http://127.0.0.1:8000/api",
        llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    )
    results = agent.run_sync()
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import random
from typing import Any

from openai import OpenAI

from outplayarena_sdk.client import ArenaClient
from outplayarena_sdk.mcp_client import MCPClient
from outplayarena_sdk.parsers import _safe_json_loads
from outplayarena_sdk.reasoning import ReasoningModerator
from outplayarena_sdk.seed import SeedResolver
from outplayarena_sdk.tools import build_backend_tools
from outplayarena_sdk.transport import AsyncBackend


def _is_queued_409(exc: Exception) -> bool:
    """Return True if *exc* is a 409 'session is queued' error."""
    resp = getattr(exc, "response", None)
    if resp is not None and getattr(resp, "status_code", None) == 409:
        try:
            detail = resp.json().get("detail", "")
            return "queued" in detail.lower()
        except Exception:
            pass
    return False


class LLMConfig:
    """Configuration for an OpenAI-compatible chat backend.

    Mirrors the dataclass that used to live in ``llm_agent.py`` so the
    per-game agents can take it as a parameter without depending on the
    legacy module.  Kept as a plain class (not a dataclass) for
    forward-compat with optional fields.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        extra_body: dict[str, Any] | None = None,
        fallback_model: str | None = None,
        max_retries: int = 2,
        reasoning_effort: str = "none",
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_body = extra_body
        self.fallback_model = fallback_model
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort


class BaseAgent:
    """Autonomous, tool-calling, reasoning-aware agent for the Arena.

    Lifecycle (in :meth:`run`):

      on_episode_start
        ↳ loop while game is not terminal and our player is in awaiting:
            on_round_start
              on_observation            (after get_observation)
                on_tool_call × N        (each LLM tool invocation)
                on_action_decision      (after parse_action)
              on_action_result          (after submit_action)
            on_message_received        (if maybe_communicate returned a message)
            on_round_end
        ↳ on_episode_end              (after get_results)

    Subclasses must override :meth:`parse_action` to convert the LLM's text
    output into the game's action format.  All other hooks have no-op
    defaults.  Per-game subclasses also override :meth:`action_format_hint`
    to inject a short description of the expected action shape into the
    LLM's system prompt and tool definition.
    """

    # ── Construction ──────────────────────────────────────────────────────

    def __init__(
        self,
        player: str,
        player_token: str,
        arena_url: str,
        llm_config: LLMConfig,
        session_id: str = "",
        *,
        mcp_url: str | None = None,
        poll_interval: float = 1.0,
        max_steps: int = 10_000,
        max_tools_per_turn: int = 4,
        use_mcp: bool = True,
        verbose: bool = False,
        seed: int | None = None,
        ready_timeout: float | None = None,
    ):
        if not session_id:
            raise ValueError(
                "session_id is required: pass the value returned by "
                "ArenaClient.create_experiment()['session_id']. The SDK "
                "treats the player_token as an opaque auth handle and never "
                "derives session_id from it."
            )
        if not player_token:
            raise ValueError(
                "player_token is required: pass the value returned by "
                "ArenaClient.create_experiment()['player_tokens'][player]."
            )
        self.player = player
        self.token = player_token
        self.arena_url = arena_url
        self.llm_config = llm_config
        self.mcp_url = mcp_url
        self.poll_interval = poll_interval
        self.max_steps = max_steps
        self.max_tools_per_turn = max_tools_per_turn
        self.use_mcp = use_mcp
        self.verbose = verbose
        self.ready_timeout = ready_timeout
        self._session_id: str | None = session_id
        self._config: dict[str, Any] | None = None
        self._seed_resolver = SeedResolver(override=seed)
        self._last_state: dict[str, Any] | None = None
        self._transport: AsyncBackend | None = None
        self._mcp_client: MCPClient | None = None
        self._mcp_connected = False
        self._openai: OpenAI | None = None
        self._reasoning: ReasoningModerator | None = None
        self._stopped = False
        self.wandb_run: dict[str, Any] | None = None

    # ── Lazy properties ───────────────────────────────────────────────────

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def config(self) -> dict[str, Any]:
        """Effective experiment config (resolved from the first backend response)."""
        if self._config is None:
            return {}
        return dict(self._config)

    @property
    def seed(self) -> int | None:
        return self._seed_resolver.seed

    @property
    def rng(self) -> random.Random:
        return self._seed_resolver.rng

    @property
    def transport(self) -> str:
        return self._transport.transport if self._transport else "uninitialized"

    # ── Lifecycle hooks (default no-ops) ──────────────────────────────────

    def on_episode_start(self, session_id: str | None, seed: int | None) -> None:
        """Called once before the per-turn loop starts."""

    def on_round_start(self, round_num: int, state: dict[str, Any]) -> None:
        """Called at the top of every poll iteration."""

    def on_observation(self, observation: dict[str, Any], state: dict[str, Any]) -> None:
        """Called after ``get_observation`` returns."""

    def on_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> None:
        """Called after each backend tool the LLM invokes."""

    def on_action_decision(self, action: Any, reasoning: str) -> None:
        """Called once per turn, after the LLM commits to an action."""

    def on_action_result(self, result: dict[str, Any], state: dict[str, Any]) -> None:
        """Called after ``submit_action`` returns."""

    def on_message_received(self, message: dict[str, Any]) -> None:
        """Called when the agent successfully sends a mailbox message."""

    def on_round_end(self, round_num: int, state: dict[str, Any]) -> None:
        """Called at the bottom of every poll iteration."""

    def on_episode_end(self, results: dict[str, Any]) -> None:
        """Called once after the game is complete."""

    def on_wandb_run_started(self, wandb_run: dict[str, Any]) -> None:
        """Called once per episode the first time W&B run metadata arrives.

        ``wandb_run`` contains: ``run_id``, ``run_name``, ``entity``,
        ``project``, ``url``.

        Override to attach your own W&B logging to the same run the platform
        opened::

            def on_wandb_run_started(self, wandb_run):
                wandb.init(
                    id=wandb_run["run_id"],
                    project=wandb_run["project"],
                    entity=wandb_run["entity"],
                    resume="allow",
                )
        """

    def on_error(self, error: Exception, context: dict[str, Any]) -> None:
        """Default: re-raise. Subclasses can swallow, log, or recover."""
        raise error

    # ── Subclass contract ────────────────────────────────────────────────

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> Any:
        """Convert the LLM's raw text into a structured game action.

        Must be overridden by per-game subclasses. Default raises so a
        missing implementation is caught on the first turn rather than
        silently producing wrong actions.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must override parse_action()"
        )

    def action_format_hint(self) -> str:
        """Short description of the action shape for the LLM.

        Injected into the system prompt and into the ``submit_action``
        tool description. Default is generic; per-game subclasses return
        something specific (e.g. ``"a Python list of N non-negative
        integers summing to TOTAL"``).
        """
        return "an action whose format depends on the game"

    def maybe_communicate(self, state: dict[str, Any]) -> str | None:
        """Optional: return a string to send to the opponent's mailbox.

        Default returns ``None`` (no message). Subclasses can override to
        add strategic communication. Called once per turn, after
        ``on_action_result``.
        """
        return None

    # ── Main entry point ──────────────────────────────────────────────────

    async def run(self) -> dict[str, Any]:
        """Run the autonomous loop until the game reaches a terminal state."""
        await self._ensure_ready()
        assert self._transport is not None

        # Wait for the session to be admitted if it's queued (#117).
        # The admission gate may return 202 with status="queued" when
        # concurrency limits are reached.  We block here until the
        # drainer promotes the session to "ready" so the agent never
        # hits a 409 on its first action submit.
        status = await self._transport.wait_for_ready(
            poll_interval=self.poll_interval,
            timeout=self.ready_timeout,
        )
        if self.verbose and status.get("queue_position", 0) > 0:
            print(f"[{self.player}] session promoted from queue (was position {status['queue_position']})")

        first_state = await self._transport.get_state()
        self._last_state = first_state
        self._resolve_config(first_state.get("config"))
        self._apply_wandb_run_meta(first_state)
        self.on_episode_start(self._session_id, self.seed)

        try:
            await self._drive_loop()
        except Exception as exc:
            self.on_error(exc, {"session_id": self._session_id, "state": self._last_state})
            raise
        finally:
            await self._teardown()

        results = await self._transport.get_results()
        self.on_episode_end(results)
        return results

    def run_sync(self) -> dict[str, Any]:
        """Synchronous wrapper around :meth:`run` for scripts and notebooks.

        Jupyter kernels already run an event loop, so a plain
        ``asyncio.run()`` would raise "cannot be called from a running
        event loop". When that's the case, drive the coroutine in a
        dedicated thread with its own loop instead.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, self.run()).result()

    # ── Loop internals ────────────────────────────────────────────────────

    async def _drive_loop(self) -> None:
        assert self._transport is not None
        step = 0
        while step < self.max_steps:
            state = self._last_state or await self._transport.get_state()
            self._last_state = state
            self._apply_wandb_run_meta(state)

            if self._is_terminal(state):
                return

            round_num = int(state.get("round") or state.get("step") or state.get("hand_number") or 0)
            self.on_round_start(round_num, state)

            if self.player in state.get("awaiting", []):
                observation = await self._fetch_observation()
                self.on_observation(observation, state)

                action, reasoning_text = await self._decide_with_tools(
                    observation=observation,
                    state=state,
                )
                self.on_action_decision(action, reasoning_text)
                result = await self._submit_action_with_retry(action)
                self.on_action_result(result, state)
                self._last_state = result

                message = self.maybe_communicate(state)
                if message:
                    sent = await self._transport.send_message(message)
                    self.on_message_received(sent)
            else:
                # Not our turn &mdash; back off until the next poll.
                await self._sleep()

            # Refresh state before round-end so on_round_end sees the latest.
            try:
                self._last_state = await self._transport.get_state()
            except Exception:
                # If the backend is briefly unavailable, keep going with
                # the last-known state; the next iteration will retry.
                pass
            self.on_round_end(round_num, self._last_state)
            step += 1
            if self._is_terminal(self._last_state):
                return
            if self.player not in (self._last_state or {}).get("awaiting", []):
                await self._sleep()

    def _is_terminal(self, state: dict[str, Any] | None) -> bool:
        if not state:
            return False
        phase = state.get("phase", "")
        if phase == "complete":
            return True
        # Some games signal completion via empty awaiting + non-playing phase.
        if not state.get("awaiting") and phase in ("complete", "finished"):
            return True
        return False

    async def _fetch_observation(self) -> dict[str, Any]:
        assert self._transport is not None
        if self._transport.mcp is not None:
            return await self._transport.get_observation()
        return await self._transport.get_observation(variant="neutral")

    async def _submit_action_with_retry(self, action: Any) -> dict[str, Any]:
        """Submit the committed action, retrying on transient failures.

        Two retry paths:

        1. **Session queued (409)**: the concurrency drainer hasn't
           promoted the session yet.  We wait for ``ready`` (up to
           ``ready_timeout``) and retry — the default is to wait
           indefinitely so the agent doesn't race ahead of its slot.

        2. **Other transient errors** (e.g. sub-second connection drop
           during a zero-downtime deploy): back off 1 s and retry once.
        """
        assert self._transport is not None
        try:
            return await self._transport.submit_action(action)
        except Exception as exc:
            if _is_queued_409(exc):
                if self.verbose:
                    print(f"[{self.player}] action rejected (session queued); waiting for promotion...")
                await self._transport.wait_for_ready(
                    poll_interval=self.poll_interval,
                    timeout=self.ready_timeout,
                )
                return await self._transport.submit_action(action)
            await asyncio.sleep(1.0)
            return await self._transport.submit_action(action)

    # ── LLM tool-calling sub-loop ─────────────────────────────────────────

    async def _decide_with_tools(
        self,
        observation: dict[str, Any],
        state: dict[str, Any],
    ) -> tuple[Any, str]:
        """Run a sub-loop where the LLM can call backend tools before committing.

        The loop terminates when:

          1. The LLM responds without any ``tool_calls`` &mdash; we
             treat the content as the action proposal and run it through
             :meth:`parse_action`.
          2. The LLM invokes ``submit_action`` &mdash; we use the
             ``allocation`` argument as the action and skip parsing.
          3. The per-turn tool budget is exhausted &mdash; we do one
             final plain-text call and parse whatever comes back.

        Two lifecycle-health measures (#127) run inside the loop: each
        iteration after the first tells the model how many tool-calling
        iterations remain, and the *last* allowed iteration forces
        ``tool_choice=submit_action`` so the turn ends via a real action
        submission rather than budget exhaustion whenever the backend
        honors ``tool_choice`` (some OpenAI-compatible backends don't;
        :meth:`_call_llm_with_tools` falls back to an unconstrained call
        if the forced call itself errors).
        """
        self._ensure_openai()
        tools = build_backend_tools(self.action_format_hint())
        system_prompt = self._compose_system_prompt()
        turn_prompt = (
            observation.get("turn")
            or observation.get("state")
            or json.dumps(observation)
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": turn_prompt},
        ]

        budget = max(1, self.max_tools_per_turn)
        last_text = ""
        while budget > 0:
            force_submit = budget == 1
            try:
                response = await asyncio.to_thread(
                    self._call_llm_with_tools, messages, tools, force_submit
                )
            except Exception as exc:
                if self.verbose:
                    print(f"[agent] LLM call failed: {exc!r}; falling back to plain text")
                response = await asyncio.to_thread(
                    self._call_llm_plain, messages
                )
            msg = response.choices[0].message
            content = msg.content or ""
            tool_calls = list(getattr(msg, "tool_calls", None) or [])

            # Terminal: no tool calls &mdash; parse the text.
            if not tool_calls:
                last_text = content
                action = self.parse_action(content, state)
                return action, content

            # Look for a submit_action call; if present, commit and stop.
            for tc in tool_calls:
                if tc.function.name == "submit_action":
                    args = _safe_json_loads(tc.function.arguments) or {}
                    allocation = args.get("allocation", args)
                    # Normalize via the per-game parser. The LLM sometimes wraps
                    # the action in a dict like {"action": "take"} or returns a
                    # list; route through parse_action (which already handles
                    # the relevant game-specific extraction) so the canonical
                    # backend format is always produced.
                    try:
                        allocation = self.parse_action(
                            json.dumps(allocation, default=str), state
                        )
                    except Exception:
                        pass
                    self.on_tool_call(tc.function.name, args, {"committed": True})
                    return allocation, content

            # Otherwise, dispatch the non-submit tool calls and loop.
            for tc in tool_calls:
                result = await self._dispatch_tool_call(tc)
                self.on_tool_call(tc.function.name, _safe_json_loads(tc.function.arguments) or {}, result)
                messages.append(_tool_call_message_to_assistant(msg, tc))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
            budget -= 1
            last_text = content
            if budget > 0:
                messages.append({
                    "role": "user",
                    "content": (
                        f"[{budget} tool-calling iteration(s) left this turn. "
                        "get_observation/get_game_state won't change unless you "
                        "act, so don't re-poll them without new information to "
                        "wait for. Call submit_action before the budget runs out.]"
                    ),
                })

        # Budget exhausted: one final plain-text call.
        try:
            response = await asyncio.to_thread(self._call_llm_plain, messages)
            last_text = response.choices[0].message.content or ""
        except Exception:
            last_text = last_text or ""
        return self.parse_action(last_text, state), last_text

    async def _dispatch_tool_call(self, tool_call: Any) -> Any:
        """Run a single tool call against the backend transport."""
        assert self._transport is not None
        name = tool_call.function.name
        args = _safe_json_loads(tool_call.function.arguments) or {}

        if name == "get_observation":
            return await self._transport.get_observation(
                variant=args.get("variant", "neutral")
            )
        if name == "get_game_state":
            return await self._transport.get_state()
        if name == "send_message":
            return await self._transport.send_message(
                content=str(args.get("content", "")),
                recipient=str(args.get("recipient", "all")),
            )
        if name == "submit_action":
            # Should be handled by the caller; if we reach here just
            # route through the transport so behavior is consistent.
            return await self._transport.submit_action(args.get("allocation", args))
        return {"error": f"unknown tool: {name}"}

    def _call_llm_with_tools(
        self, messages: list[dict], tools: list[dict], force_submit: bool = False
    ) -> Any:
        assert self._openai is not None
        kwargs: dict[str, Any] = {
            "model": self.llm_config.model,
            "messages": messages,
            "temperature": self.llm_config.temperature,
            "max_tokens": self.llm_config.max_tokens,
            "tools": tools,
        }
        if self.llm_config.extra_body:
            kwargs["extra_body"] = self.llm_config.extra_body
        if force_submit:
            # #127: force the last allowed tool-calling iteration to end the
            # turn via a real submit_action rather than budget exhaustion.
            # Not every OpenAI-compatible backend honors tool_choice the same
            # way, so if the constrained call itself errors, retry once
            # without it rather than losing tool-calling entirely.
            try:
                return self._openai.chat.completions.create(
                    tool_choice={"type": "function", "function": {"name": "submit_action"}},
                    **kwargs,
                )
            except Exception:
                pass
        return self._openai.chat.completions.create(**kwargs)

    def _call_llm_plain(self, messages: list[dict]) -> Any:
        assert self._openai is not None
        kwargs: dict[str, Any] = {
            "model": self.llm_config.model,
            "messages": messages,
            "temperature": self.llm_config.temperature,
            "max_tokens": self.llm_config.max_tokens,
        }
        if self.llm_config.extra_body:
            kwargs["extra_body"] = self.llm_config.extra_body
        return self._openai.chat.completions.create(**kwargs)

    def _compose_system_prompt(self) -> str:
        parts = [
            "You are an autonomous agent playing a game on the OutplayArena.",
            f"You are player {self.player}.",
            f"Game action format: {self.action_format_hint()}",
            "Use the provided tools to inspect the game state, communicate, and submit your action.",
        ]
        if self._reasoning is not None and self.llm_config.reasoning_effort != "none":
            parts = [self._reasoning.build_system_prompt(p) for p in parts]
        return " ".join(parts)

    # ── Setup / teardown ─────────────────────────────────────────────────

    def _ensure_openai(self) -> None:
        if self._openai is None:
            self._openai = OpenAI(
                base_url=self.llm_config.base_url,
                api_key=self.llm_config.api_key,
            )
            self._reasoning = ReasoningModerator(
                self.llm_config.model,
                effort=self.llm_config.reasoning_effort,
            )

    async def _ensure_ready(self) -> None:
        if self._transport is not None:
            return
        rest = ArenaClient(self.arena_url, session_id=self._session_id, token=self.token)
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
                self._mcp_connected = False
        self._mcp_client = mcp_client
        self._transport = AsyncBackend(rest, mcp_client, player_id=self.player)
        self._ensure_openai()

    async def _teardown(self) -> None:
        if self._mcp_client is not None and self._mcp_connected:
            try:
                self._mcp_client.disconnect()
            except Exception:
                pass
            self._mcp_connected = False

    def _resolve_config(self, config: Any) -> None:
        if isinstance(config, dict):
            self._config = config
            self._seed_resolver.resolve_from_config(config)

    def _apply_wandb_run_meta(self, state: dict[str, Any]) -> None:
        """Extract W&B run metadata from a state response and fire the hook once."""
        meta = state.get("wandb_run")
        if meta and self.wandb_run is None:
            self.wandb_run = meta
            self.on_wandb_run_started(meta)

    async def _sleep(self) -> None:
        if self.poll_interval > 0:
            await asyncio.sleep(self.poll_interval)


# ── helpers ────────────────────────────────────────────────────────────────


def _tool_call_message_to_assistant(message: Any, tool_call: Any) -> dict[str, Any]:
    """Reconstruct the assistant message with a single tool_call for the tool message reply."""
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
        ],
    }


__all__ = ["BaseAgent", "LLMConfig"]
