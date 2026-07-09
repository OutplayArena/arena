"""Tests for ArenaClient matchmaking methods (#96)."""
from unittest.mock import MagicMock

import httpx
import pytest

from outplayarena_sdk.client import ArenaClient


def _resp(payload, status_code=200):
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("GET", "http://x"),
    )


def _client():
    c = ArenaClient(base_url="http://localhost:8000/api", session_id="s1", token="nks_A")
    c.http_client = MagicMock()
    return c


def test_create_open_match():
    c = _client()
    c.http_client.post = MagicMock(
        return_value=_resp({
            "match_id": "m1",
            "invite_code": "ic-abc",
            "host_token": "nks_host",
            "host_slot": "A",
            "total_slots": 2,
            "open_slots": 1,
        })
    )
    result = c.create_open_match({"game": "ultimatum", "rounds": 10}, api_key="nk_x")
    assert result["match_id"] == "m1"
    assert result["host_token"] == "nks_host"
    c.http_client.post.assert_called_once()


def test_list_open_matches():
    c = _client()
    c.http_client.get = MagicMock(
        return_value=_resp({"matches": [{"id": "m1", "status": "waiting"}]})
    )
    result = c.list_open_matches(api_key="nk_x")
    assert len(result) == 1
    assert result[0]["id"] == "m1"


def test_get_match():
    c = _client()
    c.http_client.get = MagicMock(
        return_value=_resp({"id": "m1", "status": "running", "session_id": "s1"})
    )
    result = c.get_match("m1", api_key="nk_x")
    assert result["status"] == "running"
    assert result["session_id"] == "s1"


def test_join_match():
    c = _client()
    c.http_client.post = MagicMock(
        return_value=_resp({
            "match_id": "m1",
            "slot": "B",
            "player_token": "nks_B",
            "status": "running",
            "session_id": "s1",
        })
    )
    result = c.join_match("m1", slot="B", api_key="nk_x")
    assert result["player_token"] == "nks_B"
    assert result["session_id"] == "s1"


def test_wait_for_opponent_returns_when_running():
    c = _client()
    c.http_client.get = MagicMock(
        side_effect=[
            _resp({"id": "m1", "status": "waiting"}),
            _resp({"id": "m1", "status": "waiting"}),
            _resp({"id": "m1", "status": "running", "session_id": "s1"}),
        ]
    )
    result = c.wait_for_opponent("m1", poll_interval=0.0, timeout=10.0)
    assert result["status"] == "running"
    assert result["session_id"] == "s1"


def test_wait_for_opponent_raises_on_cancelled():
    c = _client()
    c.http_client.get = MagicMock(
        return_value=_resp({"id": "m1", "status": "cancelled"})
    )
    with pytest.raises(RuntimeError, match="cancelled"):
        c.wait_for_opponent("m1", poll_interval=0.0, timeout=5.0)


def test_wait_for_opponent_raises_on_expired():
    c = _client()
    c.http_client.get = MagicMock(
        return_value=_resp({"id": "m1", "status": "expired"})
    )
    with pytest.raises(RuntimeError, match="expired"):
        c.wait_for_opponent("m1", poll_interval=0.0, timeout=5.0)


def test_wait_for_opponent_raises_timeout():
    c = _client()
    c.http_client.get = MagicMock(
        return_value=_resp({"id": "m1", "status": "waiting"})
    )
    with pytest.raises(TimeoutError):
        c.wait_for_opponent("m1", poll_interval=0.0, timeout=0.0)