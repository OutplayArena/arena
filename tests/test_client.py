import json

import httpx
import pytest

from games.core.blotto.config import BlottoExperimentConfig
from nash_arena.client import ArenaClient


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_create_experiment_posts_config_dict_to_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"session_id": "s1"})

    client = ArenaClient("http://arena.test", http_client=mock_client(handler))

    result = client.create_experiment({"game": "blotto"})

    assert result == {"session_id": "s1"}
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/game/experiment"
    assert json.loads(requests[0].content) == {"game": "blotto"}


def test_internal_client_posts_config_to_prefixed_endpoint_with_token():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"session_id": "s1"})

    client = ArenaClient(
        "http://arena.test",
        http_client=mock_client(handler),
        game_api_prefix="/api/game",
        internal_api_token="secret",
    )

    result = client.create_experiment({"game": "blotto"})

    assert result == {"session_id": "s1"}
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/game/experiment"
    assert requests[0].headers["X-Nash-Arena-Internal-Token"] == "secret"
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
    assert requests[0].url.path == "/api/game/session/s1/state"


def test_internal_client_gets_prefixed_state_with_token():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"phase": "awaiting_action"})

    client = ArenaClient(
        "http://arena.test",
        session_id="s1",
        http_client=mock_client(handler),
        game_api_prefix="/api/game",
        internal_api_token="secret",
    )

    assert client.get_state() == {"phase": "awaiting_action"}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/game/session/s1/state"
    assert requests[0].headers["X-Nash-Arena-Internal-Token"] == "secret"


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
    assert requests[0].url.path == "/api/game/session/s1/action"
    assert requests[0].headers["Authorization"] == "Bearer tok_a"
    assert json.loads(requests[0].content) == {"allocation": [10, 0, 0]}


def test_internal_client_posts_prefixed_action_with_internal_and_bearer_tokens():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"awaiting": ["B"]})

    client = ArenaClient(
        "http://arena.test",
        session_id="s1",
        token="tok_a",
        http_client=mock_client(handler),
        game_api_prefix="/api/game",
        internal_api_token="secret",
    )

    assert client.submit_action([10, 0, 0]) == {"awaiting": ["B"]}
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/game/session/s1/action"
    assert requests[0].headers["X-Nash-Arena-Internal-Token"] == "secret"
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
    assert requests[0].url.path == "/api/game/session/s1/results"


def test_internal_client_gets_prefixed_results_with_token():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"winner": "A"})

    client = ArenaClient(
        "http://arena.test",
        session_id="s1",
        http_client=mock_client(handler),
        game_api_prefix="/api/game",
        internal_api_token="secret",
    )

    assert client.get_results() == {"winner": "A"}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/game/session/s1/results"
    assert requests[0].headers["X-Nash-Arena-Internal-Token"] == "secret"


def test_game_directory_methods_get_expected_endpoints():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": request.url.path})

    client = ArenaClient("http://arena.test", http_client=mock_client(handler))

    assert client.list_games() == {"ok": "/games"}
    assert client.get_game_details("blotto") == {"ok": "/games/blotto"}
    assert client.get_game_metrics("blotto") == {"ok": "/games/blotto/metrics"}
    assert client.get_game_prompts("blotto") == {"ok": "/games/blotto/prompts"}

    assert [request.url.path for request in requests] == [
        "/games",
        "/games/blotto",
        "/games/blotto/metrics",
        "/games/blotto/prompts",
    ]


def test_get_game_skill_gets_expected_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"game": "blotto", "skill": "Use MCP."})

    client = ArenaClient("http://arena.test", http_client=mock_client(handler))

    assert client.get_game_skill("blotto") == {
        "game": "blotto",
        "skill": "Use MCP.",
    }
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/games/blotto/skill"


def test_for_player_builds_session_bound_client():
    created = {
        "session_id": "s1",
        "player_tokens": {"A": "tok_a", "B": "tok_b"},
    }

    client = ArenaClient.for_player(
        "http://arena.test",
        created,
        "B",
        game_api_prefix="/custom/game",
        internal_api_token="secret",
    )

    assert client.base_url == "http://arena.test"
    assert client.session_id == "s1"
    assert client.token == "tok_b"
    assert client.game_api_prefix == "/custom/game"
    assert client.internal_api_token == "secret"


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
