import json

import httpx
import pytest

from blotto.client import ArenaClient
from blotto.config import BlottoExperimentConfig


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_create_experiment_posts_config_dict_to_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"session_id": "s1"})

    client = ArenaClient("http://arena.test/", http_client=mock_client(handler))

    result = client.create_experiment({"game": "blotto"})

    assert result == {"session_id": "s1"}
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/experiment"
    assert json.loads(requests[0].content) == {"game": "blotto"}


def test_create_experiment_serializes_config_object():
    requests = []
    config = BlottoExperimentConfig.classic(
        num_battlefields=2,
        total_resources=10,
        rounds=3,
    )

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"session_id": "s1"})

    client = ArenaClient("http://arena.test", http_client=mock_client(handler))

    client.create_experiment(config)

    assert json.loads(requests[0].content) == config.to_dict()


def test_get_state_requires_session_id_and_gets_state_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"phase": "awaiting_action"})

    missing_session = ArenaClient("http://arena.test", http_client=mock_client(handler))
    with pytest.raises(ValueError, match="session_id is required"):
        missing_session.get_state()

    client = ArenaClient(
        "http://arena.test",
        session_id="s1",
        http_client=mock_client(handler),
    )

    assert client.get_state() == {"phase": "awaiting_action"}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/session/s1/state"


def test_submit_action_requires_token_and_posts_bearer_action():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"awaiting": ["B"]})

    missing_token = ArenaClient(
        "http://arena.test",
        session_id="s1",
        http_client=mock_client(handler),
    )
    with pytest.raises(ValueError, match="token is required"):
        missing_token.submit_action([10, 0, 0])

    client = ArenaClient(
        "http://arena.test",
        session_id="s1",
        token="tok_a",
        http_client=mock_client(handler),
    )

    assert client.submit_action([10, 0, 0]) == {"awaiting": ["B"]}
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/session/s1/action"
    assert requests[0].headers["Authorization"] == "Bearer tok_a"
    assert json.loads(requests[0].content) == {"allocation": [10, 0, 0]}


def test_get_results_gets_results_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"winner": "A"})

    client = ArenaClient(
        "http://arena.test",
        session_id="s1",
        http_client=mock_client(handler),
    )

    assert client.get_results() == {"winner": "A"}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/session/s1/results"


def test_for_player_builds_session_bound_client():
    created = {
        "session_id": "s1",
        "player_tokens": {"A": "tok_a", "B": "tok_b"},
    }

    client = ArenaClient.for_player("http://arena.test", created, "B")

    assert client.base_url == "http://arena.test"
    assert client.session_id == "s1"
    assert client.token == "tok_b"


def test_http_errors_are_raised():
    def handler(request):
        return httpx.Response(409, json={"detail": "not complete"})

    client = ArenaClient(
        "http://arena.test",
        session_id="s1",
        http_client=mock_client(handler),
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.get_results()
