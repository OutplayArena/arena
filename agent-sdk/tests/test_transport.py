"""Tests for :mod:`outplaylabs_arena_sdk.transport`."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from outplaylabs_arena_sdk.client import ArenaClient
from outplaylabs_arena_sdk.mcp_client import MCPClient
from outplaylabs_arena_sdk.transport import AsyncBackend


@pytest.fixture
def rest():
    client = ArenaClient("http://localhost:8000/api")
    return client


class TestAsyncBackendRest:
    @pytest.mark.asyncio
    async def test_get_state(self, rest):
        rest.get_state = MagicMock(return_value={"phase": "playing", "awaiting": ["A"]})
        backend = AsyncBackend(rest)
        result = await backend.get_state()
        assert result == {"phase": "playing", "awaiting": ["A"]}
        rest.get_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_observation(self, rest):
        rest.get_observation = MagicMock(return_value={"system": "s", "turn": "t"})
        backend = AsyncBackend(rest, player_id="A")
        result = await backend.get_observation("neutral")
        assert result == {"system": "s", "turn": "t"}
        rest.get_observation.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_action(self, rest):
        rest.submit_action = MagicMock(return_value={"status": "ok"})
        backend = AsyncBackend(rest)
        result = await backend.submit_action([1, 2, 3])
        assert result == {"status": "ok"}
        rest.submit_action.assert_called_once_with([1, 2, 3])

    @pytest.mark.asyncio
    async def test_get_results(self, rest):
        rest.get_results = MagicMock(return_value={"winner": "A"})
        backend = AsyncBackend(rest)
        result = await backend.get_results()
        assert result["winner"] == "A"

    @pytest.mark.asyncio
    async def test_get_mailbox(self, rest):
        rest.get_mailbox = MagicMock(return_value=[{"id": "1", "content": "hi"}])
        backend = AsyncBackend(rest, player_id="A")
        result = await backend.get_mailbox()
        assert result == [{"id": "1", "content": "hi"}]

    @pytest.mark.asyncio
    async def test_send_message(self, rest):
        rest.send_message = MagicMock(return_value={"id": "1"})
        backend = AsyncBackend(rest, player_id="A")
        result = await backend.send_message("hello", recipient="B")
        assert result == {"id": "1"}


class TestAsyncBackendTransportSelection:
    def test_transport_is_rest_when_no_mcp(self, rest):
        backend = AsyncBackend(rest)
        assert backend.transport == "rest"

    def test_transport_is_mcp_when_mcp_provided(self, rest):
        mcp = MagicMock(spec=MCPClient)
        backend = AsyncBackend(rest, mcp)
        assert backend.transport == "mcp"


class TestAsyncBackendRestRequiresRestClient:
    def test_none_rest_client_raises(self):
        with pytest.raises(ValueError, match="rest_client is required"):
            AsyncBackend(None)
