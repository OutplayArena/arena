"""Tests for ArenaClient.get_session_status / wait_until_ready (#117)."""
from unittest.mock import MagicMock

import httpx
import pytest

from outplayarena_sdk.client import ArenaClient


def _build_client_with_responses(responses):
    """Build an ArenaClient whose http_client.get returns canned responses in order."""
    client = ArenaClient(base_url="http://localhost:8000/api", session_id="sess-1", token="nks_A")
    mock_http = MagicMock()
    mock_http.get = MagicMock(side_effect=responses)
    client.http_client = mock_http
    return client, mock_http


def _resp(payload, status_code=200):
    return httpx.Response(status_code=status_code, json=payload, request=httpx.Request("GET", "http://x"))


def test_get_session_status_returns_payload():
    client, _ = _build_client_with_responses([_resp({"status": "queued", "queue_position": 3})])
    result = client.get_session_status()
    assert result == {"status": "queued", "queue_position": 3}


def test_wait_until_ready_returns_when_promoted():
    seq = [
        _resp({"status": "queued", "queue_position": 2}),
        _resp({"status": "queued", "queue_position": 1}),
        _resp({"status": "ready", "queue_position": 0}),
    ]
    client, _ = _build_client_with_responses(seq)
    result = client.wait_until_ready(poll_interval=0.0, timeout=10.0)
    assert result["status"] == "ready"
    assert result["queue_position"] == 0


def test_wait_until_ready_returns_on_terminal_immediately():
    client, _ = _build_client_with_responses([_resp({"status": "ready", "queue_position": 0})])
    result = client.wait_until_ready(poll_interval=0.0, timeout=5.0)
    assert result["status"] == "ready"


def test_wait_until_ready_raises_timeout_when_still_queued():
    seq = [
        _resp({"status": "queued", "queue_position": 5})
    ] * 100
    client, _ = _build_client_with_responses(seq)
    with pytest.raises(TimeoutError):
        client.wait_until_ready(poll_interval=0.0, timeout=0.0)


def test_wait_until_ready_infinite_timeout(monkeypatch):
    # Avoid infinite loop: patch time.sleep to count calls, stop after 3.
    seq = [
        _resp({"status": "queued", "queue_position": 1}),
        _resp({"status": "queued", "queue_position": 1}),
        _resp({"status": "ready", "queue_position": 0}),
    ]
    client, _ = _build_client_with_responses(seq)
    result = client.wait_until_ready(poll_interval=0.0, timeout=None)
    assert result["status"] == "ready"