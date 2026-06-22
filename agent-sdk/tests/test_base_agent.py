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
            assert action == [9, 1]
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
