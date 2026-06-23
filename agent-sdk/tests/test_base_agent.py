"""Tests for :mod:`outplaylabs_arena_sdk.base` (BaseAgent).

These tests use a fully-mocked OpenAI client and a fake transport so the
agent loop can be exercised end-to-end without hitting a real backend.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from outplaylabs_arena_sdk.base import BaseAgent, LLMConfig


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_llm_config(**overrides) -> LLMConfig:
    defaults = dict(
        model="gpt-4o",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        temperature=0.0,
        max_tokens=64,
    )
    defaults.update(overrides)
    return LLMConfig(**defaults)


def _make_session_token(player: str = "A", secret: str | None = None) -> str:
    """Build a valid nks_... session key the SDK can decode.

    By default uses the same secret the SDK falls back to
    (os.environ.get("JWT_SECRET", "dev-secret-change-me")) so the test
    works regardless of the host environment.
    """
    import base64
    import hashlib
    import hmac

    if secret is None:
        secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")

    session_id = "test-session-1"
    secret_hash = hashlib.sha256(secret.encode("utf-8")).digest()
    payload = f"{session_id}:{player}"
    sig = hmac.new(secret_hash, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{session_id}:{player}:{sig}"
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"nks_{encoded}"


class _RecordingAgent(BaseAgent):
    """Test subclass that records the order of hook invocations."""

    def __init__(self, *args, actions: list[Any] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.events: list[str] = []
        self._actions = actions or [[5, 5]]
        self._action_iter = iter(self._actions)
        self._injected_state: dict[str, Any] = {}

    def on_episode_start(self, session_id, seed):
        self.events.append("on_episode_start")

    def on_round_start(self, round_num, state):
        self.events.append("on_round_start")

    def on_observation(self, observation, state):
        self.events.append("on_observation")

    def on_tool_call(self, name, arguments, result):
        self.events.append(f"on_tool_call:{name}")

    def on_action_decision(self, action, reasoning):
        self.events.append("on_action_decision")

    def on_action_result(self, result, state):
        self.events.append("on_action_result")

    def on_message_received(self, message):
        self.events.append("on_message_received")

    def on_round_end(self, round_num, state):
        self.events.append("on_round_end")

    def on_episode_end(self, results):
        self.events.append("on_episode_end")

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> Any:
        self.events.append("parse_action")
        return next(self._action_iter, self._actions[-1])

    def action_format_hint(self) -> str:
        return "a Python list of N non-negative integers."


class _PassthroughAgent(BaseAgent):
    """Test agent that does not override parse_action; passes text through verbatim.

    Useful for tests of the tool-calling sub-loop where we want to see
    the LLM's content reflected in the returned action.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events: list[str] = []

    def on_episode_start(self, session_id, seed):
        self.events.append("on_episode_start")

    def on_round_start(self, round_num, state):
        self.events.append("on_round_start")

    def on_observation(self, observation, state):
        self.events.append("on_observation")

    def on_tool_call(self, name, arguments, result):
        self.events.append(f"on_tool_call:{name}")

    def on_action_decision(self, action, reasoning):
        self.events.append("on_action_decision")

    def on_action_result(self, result, state):
        self.events.append("on_action_result")

    def on_message_received(self, message):
        self.events.append("on_message_received")

    def on_round_end(self, round_num, state):
        self.events.append("on_round_end")

    def on_episode_end(self, results):
        self.events.append("on_episode_end")

    def action_format_hint(self) -> str:
        return "a Python list of N non-negative integers."

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> Any:
        # Passthrough: tests inspect the LLM's text directly.
        return raw_text


def _mock_message(content: str = "", tool_calls: list[Any] | None = None) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


def _mock_response(content: str = "", tool_calls: list[Any] | None = None) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=_mock_message(content, tool_calls))])


def _make_fake_transport(states: list[dict]) -> MagicMock:
    """Return a MagicMock that satisfies the AsyncBackend interface."""
    transport = MagicMock()
    transport.mcp = None
    transport.get_state = AsyncMock(side_effect=states)
    transport.get_observation = AsyncMock(return_value={"system": "s", "turn": "t"})
    transport.submit_action = AsyncMock(return_value={"status": "ok"})
    transport.get_results = AsyncMock(return_value={"winner": "A"})
    return transport


# ── Construction / properties ────────────────────────────────────────────────


class TestConstruction:
    def test_player_id_extracted_from_token(self):
        agent = _RecordingAgent(
            player="ignored",
            player_token=_make_session_token("A"),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
        )
        # Token says A; player arg is overridden by the token.
        assert agent.player == "A"

    def test_seed_default_is_none(self):
        agent = _RecordingAgent(
            player="A",
            player_token=_make_session_token("A"),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
        )
        assert agent.seed is None
        assert agent.rng is not None

    def test_seed_override_seeds_rng(self):
        agent = _RecordingAgent(
            player="A",
            player_token=_make_session_token("A"),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
            seed=123,
        )
        assert agent.seed == 123
        import random
        assert agent.rng.random() == random.Random(123).random()

    def test_config_empty_until_resolved(self):
        agent = _RecordingAgent(
            player="A",
            player_token=_make_session_token("A"),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
        )
        assert agent.config == {}

    def test_session_id_extracted(self):
        agent = _RecordingAgent(
            player="A",
            player_token=_make_session_token("A"),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
        )
        assert agent.session_id == "test-session-1"


# ── Terminal detection ───────────────────────────────────────────────────────


class TestTerminalDetection:
    def _agent(self):
        return _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )

    def test_phase_complete(self):
        assert self._agent()._is_terminal({"phase": "complete"})

    def test_phase_playing_not_terminal(self):
        assert not self._agent()._is_terminal({"phase": "playing", "awaiting": ["A"]})

    def test_empty_state_not_terminal(self):
        assert not self._agent()._is_terminal({})

    def test_empty_awaiting_with_complete_phase_is_terminal(self):
        assert self._agent()._is_terminal({"phase": "complete", "awaiting": []})


# ── Loop with mocked transport + LLM ─────────────────────────────────────────


class TestRunLoop:
    @pytest.mark.asyncio
    async def test_loop_runs_through_to_completion(self):
        """End-to-end: terminal state on first poll → on_episode_start + on_episode_end."""
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
        )
        states = [
            {"phase": "complete", "awaiting": [], "round": 1, "config": {"seed": 42}},
        ]
        results = {"winner": "A"}
        transport = _make_fake_transport(states)
        transport.get_results = AsyncMock(return_value=results)

        agent._transport = transport
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(content="[5, 5]")
        )

        final = await agent.run()
        assert final == results
        assert "on_episode_start" in agent.events
        assert "on_episode_end" in agent.events
        # Seed was resolved from the first state poll.
        assert agent.seed == 42

    @pytest.mark.asyncio
    async def test_hooks_fire_in_order(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
        )
        states = [
            {"phase": "playing", "awaiting": ["A"], "round": 1, "config": {"seed": 1}},
            {"phase": "complete", "awaiting": [], "round": 1, "config": {"seed": 1}},
        ]
        transport = _make_fake_transport(states)
        transport.submit_action = AsyncMock(return_value={"status": "ok", **states[0]})
        agent._transport = transport
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(content="[5, 5]")
        )

        await agent.run()

        expected = [
            "on_episode_start",
            "on_round_start",
            "on_observation",
            "parse_action",
            "on_action_decision",
            "on_action_result",
            "on_round_end",
            "on_episode_end",
        ]
        for hook in expected:
            assert hook in agent.events, f"missing {hook} in {agent.events}"

    @pytest.mark.asyncio
    async def test_submits_action_when_in_awaiting(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
            actions=[[7, 3]],
        )
        states = [
            {"phase": "playing", "awaiting": ["A"], "round": 1, "config": {"seed": 1}},
            {"phase": "complete", "awaiting": [], "round": 1, "config": {"seed": 1}},
        ]
        transport = _make_fake_transport(states)
        agent._transport = transport
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(content="[7,3]")
        )

        await agent.run()

        transport.submit_action.assert_called_once_with([7, 3])

    @pytest.mark.asyncio
    async def test_skips_submit_when_not_in_awaiting(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
        )
        states = [
            {"phase": "playing", "awaiting": ["B"], "round": 1, "config": {"seed": 1}},
            {"phase": "complete", "awaiting": [], "round": 1, "config": {"seed": 1}},
        ]
        transport = _make_fake_transport(states)
        agent._transport = transport
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(content="[5, 5]")
        )

        await agent.run()

        # We never submitted because A wasn't in awaiting.
        transport.submit_action.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_error_default_reraises(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        boom = RuntimeError("backend down")
        transport = MagicMock()
        transport.get_state = AsyncMock(side_effect=boom)
        agent._transport = transport
        agent._openai = MagicMock()

        with pytest.raises(RuntimeError, match="backend down"):
            await agent.run()

    @pytest.mark.asyncio
    async def test_on_error_can_swallow(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
        )

        def _swallow(error, context):
            agent.events.append("on_error_swallowed")
        agent.on_error = _swallow

        states = [
            {"phase": "playing", "awaiting": ["A"], "round": 1, "config": {"seed": 1}},
            {"phase": "complete", "awaiting": [], "round": 1, "config": {"seed": 1}},
        ]
        transport = _make_fake_transport(states)
        transport.get_observation = AsyncMock(side_effect=RuntimeError("blip"))
        agent._transport = transport
        agent._openai = MagicMock()

        # on_error re-raises by default; we replaced it with a swallow. The
        # exception will still propagate from the drive loop.
        with pytest.raises(RuntimeError, match="blip"):
            await agent.run()
        assert "on_error_swallowed" in agent.events


# ── Tool-calling sub-loop ────────────────────────────────────────────────────


class TestToolCallingSubLoop:
    @pytest.mark.asyncio
    async def test_submits_via_tool_call(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        tool_call = MagicMock()
        tool_call.id = "call_1"
        tool_call.function.name = "submit_action"
        tool_call.function.arguments = '{"allocation": [9, 1]}'

        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(tool_calls=[tool_call])
        )

        with patch.object(agent, "_dispatch_tool_call", new=AsyncMock()) as dispatch:
            action, _text = await agent._decide_with_tools(
                observation={"system": "s", "turn": "t"},
                state={"phase": "playing", "awaiting": ["A"]},
            )
            # The SDK normalizes the LLM's submit_action allocation through
            # the per-game parse_action (via json.dumps). _PassthroughAgent's
            # parse_action returns the text verbatim, so the action is the
            # JSON-stringified version of the LLM's allocation.
            assert action == "[9, 1]"
            # submit_action short-circuits the loop, so no other tools are dispatched.
            dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatches_non_submit_tool_calls(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        obs_call = MagicMock()
        obs_call.id = "c1"
        obs_call.function.name = "get_observation"
        obs_call.function.arguments = '{"variant": "neutral"}'

        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(side_effect=[
            _mock_response(tool_calls=[obs_call]),
            _mock_response(content="[1, 1]"),
        ])

        with patch.object(
            agent,
            "_dispatch_tool_call",
            new=AsyncMock(return_value={"system": "s", "turn": "t"}),
        ) as dispatch:
            action, _text = await agent._decide_with_tools(
                observation={"system": "s", "turn": "t"},
                state={"phase": "playing", "awaiting": ["A"]},
            )
            # Passthrough: raw text is returned (no parse_action override).
            assert action == "[1, 1]"
            assert dispatch.call_count == 1
            dispatch.assert_called_once_with(obs_call)

    @pytest.mark.asyncio
    async def test_respects_max_tools_per_turn(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            max_tools_per_turn=2,
        )

        def _obs_call():
            tc = MagicMock()
            tc.id = "c"
            tc.function.name = "get_observation"
            tc.function.arguments = "{}"
            return tc

        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(side_effect=[
            _mock_response(tool_calls=[_obs_call()]),
            _mock_response(tool_calls=[_obs_call()]),
            _mock_response(content="[2, 2]"),
        ])

        with patch.object(
            agent,
            "_dispatch_tool_call",
            new=AsyncMock(return_value={"system": "s", "turn": "t"}),
        ) as dispatch:
            action, _text = await agent._decide_with_tools(
                observation={"system": "s", "turn": "t"},
                state={"phase": "playing", "awaiting": ["A"]},
            )
            assert action == "[2, 2]"
            assert agent._openai.chat.completions.create.call_count == 3
            assert dispatch.call_count == 2

    @pytest.mark.asyncio
    async def test_falls_back_when_provider_rejects_tools(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(side_effect=[
            TypeError("tools arg not supported"),
            _mock_response(content="[3, 3]"),
        ])

        action, _text = await agent._decide_with_tools(
            observation={"system": "s", "turn": "t"},
            state={"phase": "playing", "awaiting": ["A"]},
        )

        assert action == "[3, 3]"


# ── Additional coverage: hooks, defaults, and lifecycle edges ────────────────


class TestHookDefaults:
    """BaseAgent's default hook implementations should be no-ops (except on_error)."""

    def test_default_hooks_are_noops(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        # Calling them should not raise
        agent.on_episode_start("sess", 42)
        agent.on_round_start(1, {})
        agent.on_observation({}, {})
        agent.on_tool_call("name", {}, {})
        agent.on_action_decision([1, 2], "text")
        agent.on_action_result({}, {})
        agent.on_message_received({})
        agent.on_round_end(1, {})
        agent.on_episode_end({})

    def test_default_on_error_reraises(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        with pytest.raises(ValueError, match="boom"):
            agent.on_error(ValueError("boom"), {})

    def test_subclass_can_swallow_on_error(self):
        class _SwallowAgent(_RecordingAgent):
            def on_error(self, error, context):
                # Override to swallow.
                return None

        agent = _SwallowAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        # Should not raise.
        agent.on_error(ValueError("ignored"), {})


class TestSubclassContract:
    def test_default_parse_action_raises(self):
        """A subclass that doesn't override parse_action should raise on call."""
        class _BareAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    player="A",
                    player_token=_make_session_token(),
                    arena_url="http://x",
                    llm_config=_make_llm_config(),
                )

        agent = _BareAgent()
        with pytest.raises(NotImplementedError, match="must override parse_action"):
            agent.parse_action("text", {})

    def test_default_action_format_hint(self):
        """Default action_format_hint returns a generic description."""

        class _BareAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    player="A",
                    player_token=_make_session_token(),
                    arena_url="http://x",
                    llm_config=_make_llm_config(),
                )

        agent = _BareAgent()
        hint = agent.action_format_hint()
        assert "action" in hint.lower()

    def test_maybe_communicate_default_returns_none(self):

        class _BareAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    player="A",
                    player_token=_make_session_token(),
                    arena_url="http://x",
                    llm_config=_make_llm_config(),
                )

        agent = _BareAgent()
        assert agent.maybe_communicate({}) is None


class TestTransportProperty:
    def test_transport_uninit_before_ensure_ready(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        assert agent.transport == "uninitialized"

    def test_transport_rest_after_ensure_ready(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        # The transport property delegates to self._transport.transport,
        # so we need a mock that has a `transport` attribute.
        fake_backend = MagicMock()
        fake_backend.transport = "rest"
        agent._transport = fake_backend
        assert agent.transport == "rest"

    def test_transport_mcp_after_ensure_ready(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        fake_backend = MagicMock()
        fake_backend.transport = "mcp"
        agent._transport = fake_backend
        assert agent.transport == "mcp"


class TestSessionKeyFallback:
    def test_invalid_token_keeps_user_provided_player(self):
        """When the token can't be decoded, fall back to the user-provided player."""
        agent = _RecordingAgent(
            player="A",
            player_token="nks_not-a-valid-key",
            arena_url="http://x",
            llm_config=_make_llm_config(),
        )
        assert agent.player == "A"
        # session_id falls back to empty string when the token can't be parsed.
        assert agent.session_id == ""


class TestRunSync:
    def test_run_sync_calls_asyncio_run(self):
        agent = _RecordingAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        # Stub out run to avoid hitting the network.
        agent.run = AsyncMock(return_value={"winner": "A"})
        result = agent.run_sync()
        assert result == {"winner": "A"}


class TestMessageSending:
    @pytest.mark.asyncio
    async def test_maybe_communicate_sends_message(self):
        class _ChattyAgent(_PassthroughAgent):
            def maybe_communicate(self, state):
                return "hello there"

        agent = _ChattyAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
        )
        states = [
            {"phase": "playing", "awaiting": ["A"], "round": 1, "config": {"seed": 1}},
            {"phase": "complete", "awaiting": [], "round": 1, "config": {"seed": 1}},
        ]
        transport = _make_fake_transport(states)
        transport.send_message = AsyncMock(return_value={"id": "msg-1"})
        agent._transport = transport
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(content="[5, 5]")
        )
        await agent.run()
        transport.send_message.assert_awaited_once_with("hello there")
        assert "on_message_received" in agent.events


class TestStateRefreshError:
    @pytest.mark.asyncio
    async def test_state_refresh_error_does_not_crash_loop(self):
        """If get_state fails during round-end refresh, keep going with last-known state."""
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
        )
        states_iter = iter([
            {"phase": "playing", "awaiting": ["A"], "round": 1, "config": {"seed": 1}},
            {"phase": "playing", "awaiting": ["A"], "round": 2, "config": {"seed": 1}},
        ])
        transport = MagicMock()
        transport.mcp = None
        transport.get_state = AsyncMock(side_effect=[
            next(states_iter),
            RuntimeError("backend unavailable"),
            next(states_iter),
            {"phase": "complete", "awaiting": [], "round": 2, "config": {"seed": 1}},
        ])
        transport.get_observation = AsyncMock(return_value={"system": "s", "turn": "t"})
        transport.submit_action = AsyncMock(return_value={"status": "ok"})
        transport.get_results = AsyncMock(return_value={"winner": "A"})
        agent._transport = transport
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(content="[1, 1]")
        )
        # Should not raise despite the transient get_state error.
        await agent.run()


class TestFetchObservation:
    @pytest.mark.asyncio
    async def test_observation_passes_variant_when_no_mcp(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        transport = MagicMock()
        transport.mcp = None
        transport.get_observation = AsyncMock(return_value={"system": "s", "turn": "t"})
        agent._transport = transport
        result = await agent._fetch_observation()
        assert result == {"system": "s", "turn": "t"}
        transport.get_observation.assert_awaited_once_with(variant="neutral")

    @pytest.mark.asyncio
    async def test_observation_skips_variant_when_mcp(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        transport = MagicMock()
        transport.mcp = MagicMock()
        transport.get_observation = AsyncMock(return_value={"system": "s", "turn": "t"})
        agent._transport = transport
        await agent._fetch_observation()
        # When MCP is set, get_observation is called without variant.
        transport.get_observation.assert_awaited_once_with()


class TestDispatchToolCall:
    @pytest.mark.asyncio
    async def test_dispatch_get_observation(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        transport = MagicMock()
        transport.mcp = None
        transport.get_observation = AsyncMock(return_value={"system": "s", "turn": "t"})
        agent._transport = transport

        tc = MagicMock()
        tc.function.name = "get_observation"
        tc.function.arguments = '{"variant": "gain_framed"}'

        result = await agent._dispatch_tool_call(tc)
        assert result == {"system": "s", "turn": "t"}

    @pytest.mark.asyncio
    async def test_dispatch_get_game_state(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        state = {"phase": "playing", "round": 1}
        transport = MagicMock()
        transport.mcp = None
        transport.get_state = AsyncMock(return_value=state)
        agent._transport = transport

        tc = MagicMock()
        tc.function.name = "get_game_state"
        tc.function.arguments = "{}"

        result = await agent._dispatch_tool_call(tc)
        assert result == state

    @pytest.mark.asyncio
    async def test_dispatch_get_mailbox(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        transport = MagicMock()
        transport.mcp = None
        transport.get_mailbox = AsyncMock(return_value=[{"id": "1"}])
        agent._transport = transport

        tc = MagicMock()
        tc.function.name = "get_mailbox"
        tc.function.arguments = "{}"

        result = await agent._dispatch_tool_call(tc)
        assert result == [{"id": "1"}]

    @pytest.mark.asyncio
    async def test_dispatch_send_message(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        transport = MagicMock()
        transport.mcp = None
        transport.send_message = AsyncMock(return_value={"id": "msg-1"})
        agent._transport = transport

        tc = MagicMock()
        tc.function.name = "send_message"
        tc.function.arguments = '{"content": "hi", "recipient": "B"}'

        result = await agent._dispatch_tool_call(tc)
        assert result == {"id": "msg-1"}
        transport.send_message.assert_awaited_once_with(content="hi", recipient="B")

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        transport = MagicMock()
        transport.mcp = None
        agent._transport = transport

        tc = MagicMock()
        tc.function.name = "some_unknown_tool"
        tc.function.arguments = "{}"

        result = await agent._dispatch_tool_call(tc)
        assert "error" in result
        assert "unknown" in result["error"]


class TestComposeSystemPrompt:
    def test_basic_prompt(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        prompt = agent._compose_system_prompt()
        assert "autonomous agent" in prompt
        assert "player A" in prompt
        assert "action format" in prompt.lower()
        assert "tools" in prompt.lower()

    def test_prompt_includes_reasoning_when_enabled(self):
        cfg = _make_llm_config(reasoning_effort="medium")
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=cfg,
        )
        prompt = agent._compose_system_prompt()
        # Reasoning moderator wraps the prompt when effort != "none".
        assert "autonomous agent" in prompt


class TestEnsureReady:
    @pytest.mark.asyncio
    async def test_ensure_ready_creates_rest_transport(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
            use_mcp=False,
        )
        await agent._ensure_ready()
        assert agent._transport is not None
        assert agent._transport.mcp is None
        assert agent._openai is not None

    @pytest.mark.asyncio
    async def test_ensure_ready_falls_back_when_mcp_fails(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
            use_mcp=True,
            mcp_url="http://mcp:9999",
        )

        with patch("outplaylabs_arena_sdk.base.MCPClient") as MockMCP:
            mock_mcp = MagicMock()
            mock_mcp.connect.side_effect = RuntimeError("connection refused")
            MockMCP.return_value = mock_mcp

            await agent._ensure_ready()
            # Should fall back to REST.
            assert agent._mcp_client is None
            assert agent._mcp_connected is False
            assert agent._transport.mcp is None

    @pytest.mark.asyncio
    async def test_ensure_ready_idempotent(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://localhost:8000/api",
            llm_config=_make_llm_config(),
            use_mcp=False,
        )
        await agent._ensure_ready()
        first_transport = agent._transport
        await agent._ensure_ready()
        assert agent._transport is first_transport


class TestTeardown:
    @pytest.mark.asyncio
    async def test_teardown_disconnects_mcp(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        mock_mcp = MagicMock()
        agent._mcp_client = mock_mcp
        agent._mcp_connected = True
        await agent._teardown()
        mock_mcp.disconnect.assert_called_once()
        assert agent._mcp_connected is False

    @pytest.mark.asyncio
    async def test_teardown_handles_disconnect_error(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        mock_mcp = MagicMock()
        mock_mcp.disconnect.side_effect = RuntimeError("already closed")
        agent._mcp_client = mock_mcp
        agent._mcp_connected = True
        # Should not raise.
        await agent._teardown()

    @pytest.mark.asyncio
    async def test_teardown_noop_when_no_mcp(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
        )
        agent._mcp_client = None
        agent._mcp_connected = False
        # Should not raise.
        await agent._teardown()


class TestSleep:
    @pytest.mark.asyncio
    async def test_sleep_with_zero_poll_interval(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0,
        )
        # Should return immediately without sleeping.
        import time
        start = time.monotonic()
        await agent._sleep()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_sleep_with_positive_poll_interval(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            poll_interval=0.01,
        )
        import time
        start = time.monotonic()
        await agent._sleep()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.01


class TestLLMCallVariations:
    """Cover the extra_body branches in _call_llm_with_tools / _call_llm_plain."""

    @pytest.mark.asyncio
    async def test_extra_body_passed_to_with_tools(self):
        cfg = _make_llm_config(extra_body={"custom": "param"})
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=cfg,
        )
        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(
            return_value=_mock_response(content="[1, 1]")
        )
        await agent._decide_with_tools(
            observation={"system": "s", "turn": "t"},
            state={"phase": "playing", "awaiting": ["A"]},
        )
        call_kwargs = agent._openai.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("extra_body") == {"custom": "param"}

    @pytest.mark.asyncio
    async def test_extra_body_passed_to_plain(self):
        cfg = _make_llm_config(extra_body={"custom": "param"})
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=cfg,
        )
        agent._openai = MagicMock()
        # First call fails so we fall back to plain.
        agent._openai.chat.completions.create = MagicMock(side_effect=[
            TypeError("no tools"),
            _mock_response(content="[2, 2]"),
        ])
        await agent._decide_with_tools(
            observation={"system": "s", "turn": "t"},
            state={"phase": "playing", "awaiting": ["A"]},
        )
        # The second call (plain) should have extra_body.
        second_call = agent._openai.chat.completions.create.call_args_list[1]
        assert second_call.kwargs.get("extra_body") == {"custom": "param"}


class TestBudgetExhausted:
    @pytest.mark.asyncio
    async def test_budget_exhausted_falls_back_to_plain_text(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            max_tools_per_turn=1,
        )

        def _obs_call():
            tc = MagicMock()
            tc.id = "c"
            tc.function.name = "get_observation"
            tc.function.arguments = "{}"
            return tc

        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(side_effect=[
            _mock_response(tool_calls=[_obs_call()]),  # 1st: use budget
            _mock_response(content="[9, 9]"),          # 2nd: budget exhausted, plain
        ])

        with patch.object(
            agent, "_dispatch_tool_call", new=AsyncMock(return_value={"s": "t"})
        ):
            action, _ = await agent._decide_with_tools(
                observation={"system": "s", "turn": "t"},
                state={"phase": "playing", "awaiting": ["A"]},
            )
            assert action == "[9, 9]"

    @pytest.mark.asyncio
    async def test_budget_exhausted_with_plain_failure(self):
        agent = _PassthroughAgent(
            player="A", player_token=_make_session_token(),
            arena_url="http://x", llm_config=_make_llm_config(),
            max_tools_per_turn=1,
        )

        def _obs_call():
            tc = MagicMock()
            tc.id = "c"
            tc.function.name = "get_observation"
            tc.function.arguments = "{}"
            return tc

        agent._openai = MagicMock()
        agent._openai.chat.completions.create = MagicMock(side_effect=[
            _mock_response(tool_calls=[_obs_call()]),
            RuntimeError("LLM down"),
        ])

        with patch.object(
            agent, "_dispatch_tool_call", new=AsyncMock(return_value={"s": "t"})
        ):
            action, text = await agent._decide_with_tools(
                observation={"system": "s", "turn": "t"},
                state={"phase": "playing", "awaiting": ["A"]},
            )
            # Passthrough returns the last_text (which was the content of the
            # 1st response). On failure, last_text is preserved.
            assert action == ""
            assert text == ""
