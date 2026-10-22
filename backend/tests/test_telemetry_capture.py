"""Behavioral, privacy and transaction tests for the research event stream."""

import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from arena.models.session import SessionModel
from arena.models.telemetry_event import TelemetryEvent
from arena.session import GameSession
from arena.telemetry.capture import make_event, normalize_action, sanitize_round
from games.core.battle_of_the_sexes.config import BoSConfig
from games.core.centipede.config import CentipedeConfig
from games.core.colonelblotto.config import (
    BattlefieldConfig,
    ColonelBlottoExperimentConfig,
)
from games.core.public_goods.config import PublicGoodsConfig


def session(rounds=2):
    return GameSession.create(
        ColonelBlottoExperimentConfig(
            game="colonelblotto",
            variant="classic",
            players=2,
            budget=[10, 10],
            battlefields=[
                BattlefieldConfig(id="A", value=1.0),
                BattlefieldConfig(id="B", value=1.0),
            ],
            rounds=rounds,
            seed=42,
        ),
        agents={"A": "model-a", "B": "model-b"},
    )


def events(game_session, event_type=None):
    return [
        event
        for event in game_session._pending_telemetry
        if event_type is None or event.event_type == event_type
    ]


def restored(game_session):
    return GameSession.from_db_row(
        SessionModel(
            id=game_session.session_id,
            config_json=game_session.config.to_dict(),
            config_hash=game_session.config_hash,
            state_json=asdict(game_session.state),
            player_tokens_json=game_session.player_tokens,
            status=game_session.status,
            locked=False,
            agents_json=game_session.agents,
        )
    )


def test_actions_rounds_and_terminal_events_follow_resolution_not_submission():
    game_session = session(rounds=2)
    game_session.submit_action("A", [10, 0])
    accepted = events(game_session, "action.accepted")
    assert len(accepted) == 1
    assert accepted[0].agent_id == "model-a"
    assert accepted[0].round_number == 1
    assert accepted[0].payload_json["action"] == [10, 0]
    assert accepted[0].payload_json["server_apply_ms"] >= 0
    assert not events(game_session, "round.completed")

    game_session.submit_action("B", [0, 10])
    assert len(events(game_session, "round.completed")) == 1
    first_round = events(game_session, "round.completed")[0]
    assert first_round.round_number == 1
    assert first_round.payload_json["round"]["allocations"] == {
        "A": [10, 0],
        "B": [0, 10],
    }
    assert not events(game_session, "session.completed")

    # A new worker loads state and appends only the newly resolved round.
    game_session = restored(game_session)
    game_session.submit_action("A", [10, 0])
    game_session.submit_action("B", [0, 10])
    assert [e.round_number for e in events(game_session, "round.completed")] == [2]
    assert len(events(game_session, "session.completed")) == 1
    assert events(game_session, "session.completed")[0].payload_json == {
        "winner": "Tie",
        "total_scores": {"A": 2.0, "B": 2.0},
        "rounds_completed": 2,
    }
    with pytest.raises(ValueError):
        game_session.submit_action("A", [10, 0])
    assert len(events(game_session, "session.completed")) == 1


def test_rejections_are_observable_without_raw_actions_or_authentication_secrets():
    game_session = session()
    with pytest.raises(ValueError):
        game_session.submit_action_with_token("authorization-secret", [10, 0])
    with pytest.raises(ValueError):
        game_session.submit_action("unknown", [10, 0])
    assert not events(game_session)

    with pytest.raises(ValueError):
        game_session.submit_action_with_token(
            game_session.player_tokens["A"],
            {"api_key": "private-secret", "reasoning": "private-reasoning"},
        )
    rejected = events(game_session, "action.rejected")[0]
    assert rejected.player_id == "A"
    assert rejected.payload_json["category"] == "invalid_action"
    assert rejected.payload_json["error_type"] == "ValueError"
    assert "private" not in json.dumps(rejected.payload_json)
    assert "action" not in rejected.payload_json
    assert game_session.state.history == []

    game_session.submit_action("A", [10, 0])
    with pytest.raises(ValueError):
        game_session.submit_action("A", [10, 0])
    assert (
        events(game_session, "action.rejected")[-1].payload_json["category"]
        == "out_of_turn"
    )


def test_forfeit_records_an_action_resolved_round_and_completion_once():
    game_session = session(rounds=1)
    game_session.submit_action_with_token(
        game_session.player_tokens["A"], None, forfeit=True
    )
    action = events(game_session, "action.accepted")[0]
    assert action.payload_json["forfeit"] is True
    assert action.payload_json["action"] is None
    assert len(events(game_session, "round.completed")) == 1
    assert (
        events(game_session, "round.completed")[0].payload_json["round"]["forfeit_by"]
        == "A"
    )
    assert len(events(game_session, "session.completed")) == 1


def test_public_goods_punishment_waits_for_final_history_update():
    game_session = GameSession.create(
        PublicGoodsConfig(
            game="public_goods",
            variant="punishment",
            players=3,
            rounds=1,
            system_prompt="do-not-record-system-prompt",
        )
    )
    for player in ("A", "B", "C"):
        game_session.submit_action(player, 5)
    assert len(game_session.state.history) == 1
    assert not events(game_session, "round.completed")

    # Loading after the contribution stage must still capture the final update.
    game_session = restored(game_session)
    for player, punishment in (("A", {"B": 2}), ("B", {}), ("C", {})):
        game_session.submit_action(player, punishment)
    resolved = events(game_session, "round.completed")
    assert len(resolved) == 1
    assert resolved[0].payload_json["round"]["punishments"] == {
        "A": {"B": 2.0},
        "B": {},
        "C": {},
    }
    assert (
        resolved[0].payload_json["round"]["total_scores"]
        == game_session.state.total_scores
    )


def test_sequential_game_steps_are_actions_and_only_final_step_resolves_round():
    game_session = GameSession.create(CentipedeConfig(game="centipede", players=2))
    game_session.submit_action("A", "pass")
    assert not events(game_session, "round.completed")
    game_session.submit_action("B", "take")
    assert len(events(game_session, "action.accepted")) == 2
    assert len(events(game_session, "round.completed")) == 1


def test_configurable_bos_labels_are_canonical_game_choices():
    game_session = GameSession.create(
        BoSConfig(
            game="battle_of_the_sexes",
            players=2,
            rounds=1,
            option_a_label="custom-option-one",
            option_b_label="custom-option-two",
        )
    )
    game_session.submit_action("A", "custom-option-one")
    game_session.submit_action("B", "custom-option-one")
    assert (
        events(game_session, "action.accepted")[0].payload_json["action"] == "option_a"
    )
    assert events(game_session, "round.completed")[0].payload_json["round"][
        "actions"
    ] == {
        "A": "option_a",
        "B": "option_a",
    }


def test_failure_is_a_safe_classification_and_only_emitted_on_transition():
    game_session = session()
    game_session.mark_failed(RuntimeError("provider failed with api_key=private-key"))
    game_session.mark_failed("retry contains access-token=private-token")
    assert len(events(game_session, "session.failed")) == 1
    assert events(game_session, "session.failed")[0].payload_json == {
        "error_type": "RuntimeError",
        "category": "engine_error",
    }
    other = session()
    other.mark_failed("access-token=private-token")
    assert (
        events(other, "session.failed")[0].payload_json["error_type"]
        == "reported_failure"
    )


def test_capture_allowlists_drop_provider_text_nested_secrets_and_hidden_state():
    secret = "credential-and-reasoning-must-not-escape"
    source = {
        "round": 1,
        "allocations": {"A": [1, 2], "B": [2, 1]},
        "total_scores": {"A": 1, "B": 2, "authorization": secret},
        "system_prompt": secret,
        "reasoning": secret,
        "token": secret,
        "config": {"system_prompt": secret},
        "hole_cards": {"A": ["As", "Ks"]},
        "result": {"winner": "B", "reasoning": secret, "hands": {"A": secret}},
    }
    safe = sanitize_round(source, ("A", "B"))
    assert secret not in json.dumps(safe)
    assert "hole_cards" not in safe
    assert safe["result"] == {"winner": "B"}
    assert normalize_action(
        {"offer": 3, "api_key": secret, "action": secret}, ("A", "B")
    ) == {
        "offer": 3,
        "action": None,
    }
    assert normalize_action(float("nan")) is None
    with pytest.raises(ValueError, match="unknown telemetry"):
        make_event("session", "provider.response", {"response": secret})


def test_latency_covers_server_game_application_only(monkeypatch):
    game_session = session()
    ticks = iter((10.0, 10.025))
    monkeypatch.setattr("arena.session.perf_counter", lambda: next(ticks))
    game_session.submit_action("A", [10, 0])
    payload = events(game_session, "action.accepted")[0].payload_json
    assert payload["server_apply_ms"] == pytest.approx(25.0)
    assert "model_latency_ms" not in payload


@pytest.mark.asyncio
async def test_flush_does_not_commit_and_is_idempotent_for_same_buffer():
    game_session = session()
    game_session.submit_action("A", [10, 0])
    db = SimpleNamespace(add=Mock(), flush=AsyncMock(), commit=AsyncMock())
    await game_session.flush_telemetry(db)
    await game_session.flush_telemetry(db)
    assert db.add.call_count == 1
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()
    assert not events(game_session)


@pytest.mark.asyncio
async def test_flush_failure_keeps_pending_events_for_transaction_retry():
    game_session = session()
    game_session.submit_action("A", [10, 0])
    db = SimpleNamespace(
        add=Mock(), flush=AsyncMock(side_effect=RuntimeError("database unavailable"))
    )
    with pytest.raises(RuntimeError):
        await game_session.flush_telemetry(db)
    assert len(events(game_session)) == 1


@pytest.mark.asyncio
async def test_save_new_inserts_parent_before_event_and_commits_together():
    game_session = session()
    calls = []
    rows = []

    def add(row):
        calls.append(("add", type(row)))
        rows.append(row)

    async def flush():
        calls.append(("flush", None))

    async def commit():
        calls.append(("commit", None))

    await game_session.save_new(SimpleNamespace(add=add, flush=flush, commit=commit))
    assert calls == [
        ("add", SessionModel),
        ("flush", None),
        ("add", TelemetryEvent),
        ("flush", None),
        ("commit", None),
    ]
    creation = rows[1]
    assert creation.schema_version == 1
    assert creation.occurred_at.tzinfo is not None
    assert creation.payload_json == {
        "arena_version": creation.payload_json["arena_version"],
        "config_hash": game_session.config_hash,
        "game_type": "colonelblotto",
        "players": ["A", "B"],
        "seed": 42,
    }
    assert not events(game_session)


@pytest.mark.asyncio
async def test_save_state_commits_rejection_event_even_when_state_did_not_change():
    game_session = session()
    with pytest.raises(ValueError):
        game_session.submit_action("A", [999])
    row = SimpleNamespace()
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    db = SimpleNamespace(
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        execute=AsyncMock(return_value=result),
    )
    await game_session.save_state(db)
    db.add.assert_called_once()
    event = db.add.call_args.args[0]
    assert event.event_type == "action.rejected"
    assert row.state_json["history"] == []
    db.commit.assert_awaited_once()


def test_failed_sessions_reject_actions_and_forfeits_without_changing_state():
    game_session = session(rounds=1)
    original = asdict(game_session.state)
    game_session.mark_failed(RuntimeError("private failure detail"))
    for forfeit in (False, True):
        with pytest.raises(ValueError, match="failed"):
            game_session.submit_action_with_token(
                game_session.player_tokens["A"],
                [10, 0],
                forfeit=forfeit,
            )
    assert asdict(game_session.state) == original
    assert game_session.status == "failed"
    assert len(events(game_session, "session.failed")) == 1
    assert not events(game_session, "action.accepted")
    assert {
        event.payload_json["category"]
        for event in events(game_session, "action.rejected")
    } == {"session_failed"}


@pytest.mark.parametrize(
    ("game", "action", "expected"),
    [
        ("colonelblotto", [20, 20, 20, 20, 20], [20, 20, 20, 20, 20]),
        ("prisonersdilemma", "cooperate", "cooperate"),
        ("rock_paper_scissors", "rock", "rock"),
        ("centipede", "take", "take"),
        ("battle_of_the_sexes", "opera", "option_a"),
        ("ultimatum", "accept", "accept"),
        ("cournot_duopoly", 5, 5),
        ("public_goods", 5, 5),
        ("texas_hold_em", "fold", "fold"),
        ("stag_hunt", "stag", "stag"),
        ("chicken_game", "dare", "dare"),
        ("vickrey_auction", 5, 5),
    ],
)
def test_all_registered_games_preserve_normalized_choices_and_match_engine_winner(
    game, action, expected
):
    from arena.game_registry import GameRegistry

    config = GameRegistry().config_from_request(
        {
            "game": game,
            "players": 3 if game in ("public_goods", "vickrey_auction") else 2,
            "rounds": 1,
            "seed": 42,
        }
    )
    game_session = GameSession.create(config)
    for _ in range(10):
        if game_session.status == "completed":
            break
        state = asdict(game_session.state)
        player = (state.get("awaiting") or [state.get("current_player")])[0]
        chosen = (
            5
            if game == "ultimatum" and state["phase"] == "awaiting_proposal"
            else action
        )
        game_session.submit_action_with_token(
            game_session.player_tokens[player], chosen
        )
    assert game_session.status == "completed"
    assert (
        events(game_session, "action.accepted")[-1].payload_json["action"] == expected
    )
    assert len(events(game_session, "round.completed")) == 1
    assert (
        events(game_session, "session.completed")[0].payload_json["winner"]
        == game_session.results()["winner"]
    )
    if game == "chicken_game":
        assert events(game_session, "round.completed")[0].payload_json["round"][
            "actions"
        ] == {
            "A": "dare",
            "B": "dare",
        }
    if game == "vickrey_auction":
        assert (
            events(game_session, "round.completed")[0].payload_json["round"]["values"]
            == game_session.state.history[0]["values"]
        )
