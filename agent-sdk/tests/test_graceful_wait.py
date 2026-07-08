"""Tests for graceful session-ready waiting (#117).

Covers:
- AsyncBackend.wait_for_ready (polling, timeout, infinite)
- _is_queued_409 helper
- BaseAgent._submit_action_with_retry (409 → wait → retry)
- quick_play (wait after queued experiment creation)
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from outplayarena_sdk.base import _is_queued_409
from outplayarena_sdk.client import ArenaClient
from outplayarena_sdk.transport import AsyncBackend


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resp(payload, status_code=200):
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("GET", "http://x"),
    )


def _mock_rest_with_status_responses(responses):
    """Build an ArenaClient whose get_session_status returns canned responses."""
    client = ArenaClient(
        base_url="http://localhost:8000/api",
        session_id="sess-1",
        token="nks_A",
    )
    mock_http = MagicMock()
    mock_http.get = MagicMock(side_effect=responses)
    client.http_client = mock_http
    return client


# ── AsyncBackend.wait_for_ready ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_for_ready_polls_until_promoted():
    seq = [
        _resp({"status": "queued", "queue_position": 2}),
        _resp({"status": "queued", "queue_position": 1}),
        _resp({"status": "ready", "queue_position": 0}),
    ]
    rest = _mock_rest_with_status_responses(seq)
    transport = AsyncBackend(rest)
    result = await transport.wait_for_ready(poll_interval=0.0, timeout=10.0)
    assert result["status"] == "ready"
    assert result["queue_position"] == 0


@pytest.mark.asyncio
async def test_wait_for_ready_returns_immediately_when_not_queued():
    rest = _mock_rest_with_status_responses([
        _resp({"status": "ready", "queue_position": 0})
    ])
    transport = AsyncBackend(rest)
    result = await transport.wait_for_ready(poll_interval=0.0, timeout=5.0)
    assert result["status"] == "ready"


@pytest.mark.asyncio
async def test_wait_for_ready_raises_timeout():
    rest = _mock_rest_with_status_responses([
        _resp({"status": "queued", "queue_position": 5})
    ] * 100)
    transport = AsyncBackend(rest)
    with pytest.raises(TimeoutError):
        await transport.wait_for_ready(poll_interval=0.0, timeout=0.0)


@pytest.mark.asyncio
async def test_wait_for_ready_infinite_timeout():
    seq = [
        _resp({"status": "queued", "queue_position": 1}),
        _resp({"status": "queued", "queue_position": 1}),
        _resp({"status": "ready", "queue_position": 0}),
    ]
    rest = _mock_rest_with_status_responses(seq)
    transport = AsyncBackend(rest)
    result = await transport.wait_for_ready(poll_interval=0.0, timeout=None)
    assert result["status"] == "ready"


# ── _is_queued_409 ───────────────────────────────────────────────────────────


def test_is_queued_409_detects_queued_response():
    resp = httpx.Response(
        status_code=409,
        json={"detail": "session is queued waiting for a concurrency slot"},
        request=httpx.Request("POST", "http://x"),
    )
    exc = httpx.HTTPStatusError("conflict", request=resp.request, response=resp)
    assert _is_queued_409(exc) is True


def test_is_queued_409_rejects_non_queued_409():
    resp = httpx.Response(
        status_code=409,
        json={"detail": "already submitted"},
        request=httpx.Request("POST", "http://x"),
    )
    exc = httpx.HTTPStatusError("conflict", request=resp.request, response=resp)
    assert _is_queued_409(exc) is False


def test_is_queued_409_rejects_non_409():
    resp = httpx.Response(
        status_code=500,
        json={"detail": "internal error"},
        request=httpx.Request("POST", "http://x"),
    )
    exc = httpx.HTTPStatusError("error", request=resp.request, response=resp)
    assert _is_queued_409(exc) is False


def test_is_queued_409_rejects_plain_exception():
    assert _is_queued_409(ValueError("not an httpx error")) is False


# ── BaseAgent._submit_action_with_retry (409 → wait → retry) ─────────────────


@pytest.mark.asyncio
async def test_submit_action_retries_after_queued_409():
    """When submit_action raises a 409 'queued' error, the agent waits
    for the session to be promoted and then retries successfully."""
    from outplayarena_sdk.base import BaseAgent

    # Build a minimal agent instance (we only test _submit_action_with_retry)
    agent = BaseAgent.__new__(BaseAgent)
    agent.player = "A"
    agent.verbose = False
    agent.poll_interval = 0.0
    agent.ready_timeout = 10.0
    agent._transport = MagicMock()

    # First call raises 409 "queued", second succeeds
    queued_resp = httpx.Response(
        status_code=409,
        json={"detail": "session is queued waiting for a concurrency slot"},
        request=httpx.Request("POST", "http://x"),
    )
    queued_exc = httpx.HTTPStatusError("conflict", request=queued_resp.request, response=queued_resp)

    agent._transport.submit_action = AsyncMock(
        side_effect=[queued_exc, {"status": "ok"}]
    )
    agent._transport.wait_for_ready = AsyncMock(return_value={"status": "ready", "queue_position": 0})

    result = await agent._submit_action_with_retry([20, 20, 20, 20, 20])
    assert result == {"status": "ok"}
    # wait_for_ready was called
    agent._transport.wait_for_ready.assert_called_once()


@pytest.mark.asyncio
async def test_submit_action_retries_once_on_non_queued_error():
    """Non-409 errors fall back to the existing retry-once-after-backoff path."""
    from outplayarena_sdk.base import BaseAgent

    agent = BaseAgent.__new__(BaseAgent)
    agent.player = "A"
    agent.verbose = False
    agent.poll_interval = 0.0
    agent.ready_timeout = 10.0
    agent._transport = MagicMock()

    agent._transport.submit_action = AsyncMock(
        side_effect=[ConnectionError("transient"), {"status": "ok"}]
    )
    agent._transport.wait_for_ready = AsyncMock(return_value={"status": "ready"})

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await agent._submit_action_with_retry([20, 20, 20, 20, 20])
    assert result == {"status": "ok"}
    # wait_for_ready was NOT called (not a queued 409)
    agent._transport.wait_for_ready.assert_not_called()


# ── quick_play waits after queued experiment ─────────────────────────────────


def test_quick_play_waits_when_session_queued():
    """quick_play calls wait_until_ready when POST /experiment returns 202."""
    from outplayarena_sdk import quick_play

    created_response = {
        "session_id": "sess-123",
        "player_tokens": {"A": "nks_A", "B": "nks_B"},
        "status": "queued",
        "queue_position": 1,
        "max_concurrent_sessions": 1,
        "max_concurrent_sessions_per_user": 5,
        "config_hash": "abc",
        "arena_version": "1.0",
        "config": {},
    }

    with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.create_experiment.return_value = created_response
        mock_instance.wait_until_ready.return_value = {"status": "ready", "queue_position": 0}

        # Patch agent_cls to avoid real agent startup
        with patch("outplayarena_sdk.quick_play.get_agent_class") as mock_cls:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value={"winner": "A"})
            mock_cls.return_value = MagicMock(return_value=mock_agent)

            result = quick_play(
                game="colonelblotto",
                agents={"A": {"model": "x", "api_key": "k"}},
                arena_url="http://localhost:8000/api",
                config={"rounds": 1},
                mcp_url="",
                ready_timeout=30.0,
            )

            # wait_until_ready was called with timeout=30.0
            mock_instance.wait_until_ready.assert_called_once_with(timeout=30.0)
            assert result["winner"] == "A"


def test_quick_play_skips_wait_when_session_not_queued():
    """quick_play does NOT call wait_until_ready when status is 'ready'."""
    from outplayarena_sdk import quick_play

    created_response = {
        "session_id": "sess-456",
        "player_tokens": {"A": "nks_A", "B": "nks_B"},
        "status": "ready",
        "config_hash": "abc",
        "arena_version": "1.0",
        "config": {},
    }

    with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.create_experiment.return_value = created_response

        with patch("outplayarena_sdk.quick_play.get_agent_class") as mock_cls:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value={"winner": "B"})
            mock_cls.return_value = MagicMock(return_value=mock_agent)

            result = quick_play(
                game="colonelblotto",
                agents={"A": {"model": "x", "api_key": "k"}},
                arena_url="http://localhost:8000/api",
                config={"rounds": 1},
                mcp_url="",
            )

            mock_instance.wait_until_ready.assert_not_called()
            assert result["winner"] == "B"
