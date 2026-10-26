"""Research access uses owner credentials, separate from game capabilities."""

from unittest.mock import MagicMock

import httpx
import pytest
from outplayarena_sdk.client import ArenaClient


def response(payload, status=200):
    return httpx.Response(
        status, json=payload, request=httpx.Request("GET", "http://arena")
    )


def client():
    transport = MagicMock()
    return ArenaClient(
        "http://arena/api", "run-1", token="player-secret", http_client=transport
    ), transport


def test_report_uses_owner_credential_not_player_token():
    arena, transport = client()
    transport.get.return_value = response({"schema_version": 1})
    assert arena.get_telemetry(api_key="owner-secret") == {"schema_version": 1}
    assert transport.get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer owner-secret"
    }
    assert transport.get.call_args.args[0].endswith("/run-1/telemetry")


def test_event_iteration_preserves_filter_and_cursor_between_pages():
    arena, transport = client()
    transport.get.side_effect = [
        response({"events": [{"id": 3}], "next_after_id": 3}),
        response({"events": [{"id": 8}], "next_after_id": None}),
    ]
    assert list(
        arena.iter_telemetry_events(
            api_key="owner-secret", event_type="action.rejected", page_size=1
        )
    ) == [{"id": 3}, {"id": 8}]
    calls = transport.get.call_args_list
    assert calls[0].kwargs["params"] == {
        "after_id": 0,
        "limit": 1,
        "event_type": "action.rejected",
    }
    assert calls[1].kwargs["params"]["after_id"] == 3
    assert calls[1].kwargs["headers"]["Authorization"] == "Bearer owner-secret"


def test_event_iteration_stops_on_empty_last_page():
    arena, transport = client()
    transport.get.return_value = response({"events": [], "next_after_id": None})
    assert list(arena.iter_telemetry_events(api_key="owner-secret")) == []
    assert transport.get.call_count == 1


def test_event_iteration_detects_stalled_cursor():
    arena, transport = client()
    transport.get.return_value = response({"events": [], "next_after_id": 0})
    with pytest.raises(RuntimeError, match="cursor"):
        list(arena.iter_telemetry_events(api_key="owner-secret"))


@pytest.mark.parametrize("page_size", [0, 501])
def test_event_iteration_rejects_unbounded_page_size(page_size):
    arena, transport = client()
    with pytest.raises(ValueError, match="page_size"):
        list(arena.iter_telemetry_events(api_key="owner", page_size=page_size))
    transport.get.assert_not_called()


def test_telemetry_propagates_access_failure():
    arena, transport = client()
    transport.get.return_value = response({"detail": "session not found"}, status=404)
    with pytest.raises(httpx.HTTPStatusError):
        arena.get_telemetry(api_key="other-owner")


def test_telemetry_requires_owner_credential():
    arena, transport = client()
    with pytest.raises(ValueError, match="owner"):
        arena.get_telemetry(api_key=" ")
    transport.get.assert_not_called()


def test_event_iteration_requires_owner_credential():
    arena, transport = client()
    with pytest.raises(ValueError, match="owner"):
        list(arena.iter_telemetry_events(api_key=" "))
    transport.get.assert_not_called()
