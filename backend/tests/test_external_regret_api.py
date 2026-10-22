"""The completed-session HTTP response and SDK retain exact regret results."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from arena.game_registry import GameRegistry
from arena.session import GameSession
from fastapi.testclient import TestClient
from outplayarena_sdk.client import ArenaClient
from outplayarena_sdk.results import format_results, save_results


@pytest.mark.parametrize(
    "slug,actions",
    [
        ("rock_paper_scissors", ("rock", "paper")),
        ("prisonersdilemma", ("cooperate", "defect")),
        ("stag_hunt", ("stag", "hare")),
    ],
)
@pytest.mark.parametrize("forfeit", [False, True])
def test_results_http_and_sdk_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    slug: str,
    actions: tuple,
    forfeit: bool,
) -> None:
    from arena import main

    config = GameRegistry().config_from_request({"game": slug, "rounds": 1})
    session = GameSession.create(config, agents={"A": "alice", "B": "bob"})
    if forfeit:
        session.state = session.game.forfeit_round(session.state, "A")
    else:
        session.submit_action("A", actions[0])
        session.submit_action("B", actions[1])
    monkeypatch.setattr(main, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(main, "get_all_registries", dict)
    db = SimpleNamespace(execute=AsyncMock(return_value=MagicMock()))
    db.execute.return_value.scalar_one_or_none.return_value = None
    previous = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[main.get_db] = lambda: db
    try:
        http = TestClient(main.app)
        sdk = ArenaClient(
            "http://testserver", session_id=session.session_id, http_client=http
        )
        result = sdk.get_results()
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)
    role_metric = result["metrics"]["external_regret"]["A"]
    rich_metric = result["rich_metrics"]["agents"]["alice"]["external_regret"]
    assert role_metric == rich_metric
    assert role_metric["status"] == ("unavailable" if forfeit else "available")
    assert "cumulative_regret" in result["rich_metrics"]["agents"]["alice"]
    assert result["config"] == config.to_dict()
    assert "external_regret" in format_results(result)
    import json

    saved = save_results(result, tmp_path)
    assert json.loads(saved.read_text())["results"] == result


def test_namespacing_preserves_unavailability_evidence() -> None:
    from arena.main import _namespace_match

    config = GameRegistry().config_from_request({"game": "stag_hunt", "rounds": 1})
    session = GameSession.create(config)
    session.state = session.game.forfeit_round(session.state, "A")
    match = _namespace_match(session.to_match(), "researcher")
    metric = session.game.metrics_engine.compute_external_regret(
        match, "A@researcher", match.config
    )
    assert metric["status"] == "unavailable"
    assert "forfeit" in metric["reason"]
    assert match.metadata == session.to_match().metadata


@pytest.mark.parametrize(
    "slug,action", [("prisonersdilemma", "cooperate"), ("stag_hunt", "stag")]
)
def test_noisy_session_result_unavailable(
    monkeypatch: pytest.MonkeyPatch, slug: str, action: str
) -> None:
    from arena import main

    cfg = GameRegistry().config_from_request(
        {"game": slug, "rounds": 1, "noise": 0.5, "seed": 3}
    )
    session = GameSession.create(cfg)
    session.submit_action("A", action)
    session.submit_action("B", action)
    monkeypatch.setattr(main, "get_session", AsyncMock(return_value=session))
    monkeypatch.setattr(main, "get_all_registries", dict)
    db = SimpleNamespace(execute=AsyncMock(return_value=MagicMock()))
    db.execute.return_value.scalar_one_or_none.return_value = None
    previous = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[main.get_db] = lambda: db
    try:
        response = TestClient(main.app).get(f"/session/{session.session_id}/results")
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)
    assert response.status_code == 200
    assert (
        "noise"
        in response.json()["rich_metrics"]["agents"]["A"]["external_regret"]["reason"]
    )
