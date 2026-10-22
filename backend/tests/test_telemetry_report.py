from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from arena.telemetry.report import build_report, safe_config


def row(**changes):
    values = {
        "id": "research-session",
        "status": "completed",
        "user_id": "owner",
        "config_json": {
            "game": "rock_paper_scissors",
            "players": 2,
            "rounds": 6,
            "seed": 7,
        },
        "config_hash": "sha256:example",
        "agents_json": {"A": "agent-a", "B": "agent-b"},
        "player_tokens_json": {
            "A": "secret-session-key-a",
            "B": "secret-session-key-b",
        },
        "state_json": {
            "phase": "complete",
            "history": [{"round": 1, "total_scores": {"A": 4, "B": 2}}],
            "total_scores": {"A": 4, "B": 2},
        },
    }
    values.update(changes)
    return SimpleNamespace(**values)


def event(event_type, payload=None, player_id=None, event_id=1):
    return SimpleNamespace(
        id=event_id,
        schema_version=1,
        session_id="research-session",
        event_type=event_type,
        payload_json=payload or {},
        player_id=player_id,
        agent_id=f"agent-{player_id.lower()}" if player_id else None,
        round_number=1,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def created():
    return event(
        "session.created", {"arena_version": "0.4.0", "players": ["A", "B"], "seed": 7}
    )


def completed():
    return event(
        "session.completed",
        {"winner": "A", "total_scores": {"A": 4, "B": 2}, "rounds_completed": 6},
    )


def test_report_counts_latency_and_consecutive_repetition():
    events = [created()]
    events += [
        event("action.accepted", {"action": "rock", "server_apply_ms": latency}, "A")
        for latency in [1, 2, 3, 4, 5]
    ]
    events += [
        event(
            "action.accepted",
            {"action": None, "forfeit": True, "server_apply_ms": 9},
            "A",
        ),
        event(
            "action.rejected",
            {
                "category": "invalid_action",
                "error_type": "ValueError",
                "server_apply_ms": 50,
            },
            "A",
        ),
        event("action.accepted", {"action": "scissors", "server_apply_ms": 4}, "B"),
        completed(),
    ]
    report = build_report(row(), events)
    a, b = report["players"]
    assert report["schema_version"] == 1
    assert report["provenance"]["arena_version"] == "0.4.0"
    assert report["coverage"] == {
        "event_count": 10,
        "recorded_actions": 7,
        "history_rounds": 1,
        "history_entries": 1,
        "legacy": False,
        "complete": True,
        "action_source": "events",
    }
    assert report["summary"] == {
        "rounds_completed": 6,
        "action_count": 7,
        "rejected_actions": 1,
        "forfeits": 1,
        "scores": {"A": 4, "B": 2},
        "winner": "A",
    }
    assert a["accepted_actions"] == 6
    assert a["rejected_actions"] == 1
    assert a["forfeits"] == 1
    assert a["mean_apply_latency_ms"] == 4
    assert a["action_distribution"] == [{"action": '"rock"', "count": 5}]
    assert a["repeated_action_rate"] == 1
    assert b["repeated_action_rate"] is None
    assert {p["code"] for p in report["patterns"]} == {
        "rejected_actions",
        "forfeits",
        "repeated_actions",
    }


def test_repetition_is_adjacent_not_just_most_common_frequency():
    actions = ["rock", "paper", "rock", "paper", "rock"]
    report = build_report(
        row(),
        [
            created(),
            *[event("action.accepted", {"action": action}, "A") for action in actions],
            completed(),
        ],
    )
    assert report["players"][0]["repeated_action_rate"] == 0
    assert "repeated_actions" not in [pattern["code"] for pattern in report["patterns"]]


def test_small_samples_do_not_emit_repetition_pattern():
    report = build_report(
        row(),
        [
            created(),
            event("action.accepted", {"action": "rock"}, "A"),
            event("action.accepted", {"action": "rock"}, "A"),
            completed(),
        ],
    )
    assert report["players"][0]["repeated_action_rate"] == 1
    assert "repeated_actions" not in [pattern["code"] for pattern in report["patterns"]]


def test_legacy_means_unavailable_observations_not_perfect_performance():
    report = build_report(row(status="failed"))
    assert report["coverage"]["legacy"] is True
    assert report["coverage"]["complete"] is False
    assert report["coverage"]["action_source"] == "unavailable"
    assert report["coverage"]["recorded_actions"] == 0
    assert report["summary"]["action_count"] is None
    assert report["summary"]["rejected_actions"] is None
    assert report["summary"]["forfeits"] is None
    assert report["summary"]["scores"] == {"A": 4, "B": 2}
    assert report["summary"]["winner"] is None
    assert report["provenance"]["arena_version"] is None
    for player in report["players"]:
        assert player["accepted_actions"] is None
        assert player["mean_apply_latency_ms"] is None
        assert player["repeated_action_rate"] is None
    assert [p["code"] for p in report["patterns"]] == ["capture_incomplete"]


def test_partial_instrumentation_marks_counts_as_observed():
    report = build_report(
        row(), [event("action.accepted", {"action": "rock"}, "A"), completed()]
    )
    assert report["coverage"]["legacy"] is False
    assert report["coverage"]["complete"] is False
    assert report["summary"]["action_count"] == 1
    assert report["provenance"]["arena_version"] is None
    assert report["patterns"][0]["code"] == "capture_incomplete"


def test_redaction_excludes_credentials_prompts_messages_and_unknown_action_fields():
    import json

    cfg = {
        "game": "rock_paper_scissors",
        "players": 2,
        "seed": 7,
        "system_prompt": "TOP_SECRET",
        "api_key": "TOP_SECRET",
        "runtime": {"password": "TOP_SECRET"},
        "battlefields": [
            {
                "id": "hill",
                "value": 1,
                "token": "TOP_SECRET",
                "nested": {"prompt": "TOP_SECRET"},
            }
        ],
        "option_a_label": "TOP_SECRET",
    }
    report = build_report(
        row(config_json=cfg),
        [
            created(),
            event(
                "action.accepted",
                {
                    "action": {"action": "rock", "api_key": "TOP_SECRET"},
                    "prompt": "TOP_SECRET",
                    "server_apply_ms": float("inf"),
                },
                "A",
            ),
            completed(),
        ],
    )
    serialized = json.dumps(report, allow_nan=False)
    assert "TOP_SECRET" not in serialized
    assert "secret-session-key" not in serialized
    assert report["provenance"]["config"] == safe_config(cfg)
    assert report["players"][0]["mean_apply_latency_ms"] is None


def test_normalized_structured_actions_are_canonical():
    report = build_report(
        row(),
        [
            created(),
            event(
                "action.accepted",
                {"action": {"raise_amount": 5, "action": "raise"}},
                "A",
            ),
            event(
                "action.accepted",
                {"action": {"action": "raise", "raise_amount": 5}},
                "A",
            ),
            completed(),
        ],
    )
    assert report["players"][0]["action_distribution"] == [
        {"action": '{"action":"raise","raise_amount":5}', "count": 2}
    ]


def test_detector_extension_receives_sanitized_report():
    def custom_detector(report):
        assert "player_tokens" not in report
        yield {
            "code": "custom",
            "severity": "info",
            "title": "Custom observation",
            "detail": "For this study.",
            "evidence": {"game": report["game"]},
        }

    report = build_report(row(status="failed"), detectors=[custom_detector])
    assert [p["code"] for p in report["patterns"]] == ["custom"]


@pytest.mark.parametrize("status", ["ready", "running", "queued"])
def test_report_refuses_active_hidden_actions(status):
    with pytest.raises(ValueError, match="after the session"):
        build_report(
            row(status=status), [event("action.accepted", {"action": "rock"}, "A")]
        )


def test_failed_pgg_interim_history_is_not_a_completed_round():
    report = build_report(
        row(
            status="failed",
            state_json={
                "history": [{"round": 1, "contributions": {"A": 2}}],
                "total_scores": {"A": 0, "B": 0},
            },
        )
    )
    assert report["summary"]["rounds_completed"] == 0
    assert report["coverage"]["history_rounds"] == 0
    assert report["coverage"]["history_entries"] == 1


def test_centipede_steps_are_distinct_from_one_finalized_result():
    report = build_report(
        row(
            status="failed",
            state_json={
                "history": [
                    {"step": 1, "player": "A", "action": "pass"},
                    {"step": 2, "player": "B", "action": "pass"},
                    {
                        "step": 3,
                        "player": "A",
                        "action": "take",
                        "total_scores": {"A": 16, "B": 4},
                    },
                ],
                "total_scores": {"A": 16, "B": 4},
            },
        )
    )
    assert report["summary"]["rounds_completed"] == 1
    assert report["coverage"]["history_rounds"] == 1
    assert report["coverage"]["history_entries"] == 3


def test_large_finite_integer_scores_do_not_overflow_float_conversion():
    score = 10**400
    report = build_report(
        row(
            status="failed",
            state_json={
                "history": [],
                "total_scores": {"A": score, "B": 0},
            },
        )
    )
    assert report["summary"]["scores"]["A"] == score
