"""Explicit schemas for research capture, independent of agent/provider logging.

Only normalized game actions and allowlisted resolved results enter this stream.
Raw requests, messages, prompts, reasoning, credentials and provider responses
are deliberately never copied. New games can extend the action/result allowlists
after reviewing their data contract.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from arena.models.telemetry_event import TelemetryEvent

SCHEMA_VERSION = 1
EVENT_TYPES = frozenset(
    {
        "session.created",
        "action.accepted",
        "action.rejected",
        "round.completed",
        "session.completed",
        "session.failed",
    }
)
ACTION_VALUES = frozenset(
    {
        "cooperate",
        "defect",
        "rock",
        "paper",
        "scissors",
        "take",
        "pass",
        "fold",
        "check",
        "call",
        "raise",
        "stag",
        "hare",
        "accept",
        "reject",
        "option_a",
        "option_b",
        "opera",
        "football",
        "swerve",
        "dare",
    }
)
ACTION_FIELDS = frozenset(
    {
        "action",
        "move",
        "offer",
        "amount",
        "accept",
        "response",
        "quantity",
        "contribution",
        "punishment",
        "raise_amount",
    }
)
ERROR_CATEGORIES = frozenset(
    {
        "invalid_action",
        "out_of_turn",
        "session_complete",
        "unsupported_action",
        "engine_error",
        "session_failed",
    }
)


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int):
        return value
    return value if math.isfinite(value) else None


def normalize_action(
    value: Any,
    player_ids: tuple[str, ...] | list[str] = (),
    choices: dict[str, str] | None = None,
) -> Any:
    """Keep numeric/finite game actions and known choices, never arbitrary text."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if choices and value in choices:
            return choices[value]
        if text in ACTION_VALUES:
            return text
        try:
            return _number(float(text))
        except ValueError:
            return None
    if isinstance(value, (list, tuple)):
        return [normalize_action(item, player_ids, choices) for item in value]
    if isinstance(value, dict):
        allowed = ACTION_FIELDS | set(player_ids)
        return {
            key: normalize_action(item, player_ids, choices)
            for key, item in value.items()
            if key in allowed
        }
    return None


def _scores(value: Any, player_ids: tuple[str, ...] | list[str]) -> dict:
    if not isinstance(value, dict):
        return {}
    return {
        key: _number(item)
        for key, item in value.items()
        if key in player_ids and _number(item) is not None
    }


def _player(value: Any, player_ids: tuple[str, ...] | list[str]) -> str | None:
    return (
        value
        if isinstance(value, str) and value in {*player_ids, "Tie", "forced"}
        else None
    )


def sanitize_round(
    record: dict,
    player_ids: tuple[str, ...] | list[str] = (),
    choices: dict[str, str] | None = None,
) -> dict:
    """Extract resolved objective game data; omit hidden cards and free text."""
    if not isinstance(record, dict):
        return {}
    clean: dict[str, Any] = {}
    for key in (
        "round",
        "hand",
        "step",
        "offer",
        "offer_fraction",
        "price",
        "total_quantity",
        "pool",
        "total_pool",
        "share",
        "pot",
        "pot_a_before",
        "pot_b_before",
        "pot_a_after",
        "pot_b_after",
    ):
        if key in record and _number(record[key]) is not None:
            clean[key] = _number(record[key])
    for key in ("accepted", "coordinated", "forfeit"):
        if isinstance(record.get(key), bool):
            clean[key] = record[key]
    for key in (
        "winner",
        "player",
        "proposer",
        "responder",
        "forfeit_by",
        "game_ended_by",
    ):
        if key in record and _player(record[key], player_ids) is not None:
            clean[key] = record[key]
    for key in (
        "scores",
        "payoffs",
        "total_scores",
        "round_payoffs",
        "contributions",
        "quantities",
        "punishment_costs",
        "punishment_received",
        "chips_after",
        "preflop_equity",
        "values",
    ):
        if isinstance(record.get(key), dict):
            clean[key] = _scores(record[key], player_ids)
    for key in ("actions", "allocations", "intended_actions", "punishments"):
        if isinstance(record.get(key), dict):
            clean[key] = {
                player: normalize_action(action, player_ids, choices)
                for player, action in record[key].items()
                if player in player_ids
            }
    for key in ("action", "response"):
        if key in record:
            clean[key] = normalize_action(record[key], player_ids, choices)
    if isinstance(record.get("forfeits"), list):
        clean["forfeits"] = [
            player for player in record["forfeits"] if player in player_ids
        ]
    if isinstance(record.get("outcome"), str) and record.get("outcome") in {
        "CC",
        "CD",
        "DC",
        "DD",
        "SS",
        "SH",
        "HS",
        "HH",
        "AA",
        "AB",
        "BA",
        "BB",
        "DS",
        "SD",
        "fold",
        "showdown",
        "forfeit",
    }:
        clean["outcome"] = record["outcome"]
    if isinstance(record.get("street"), str) and record.get("street") in {
        "preflop",
        "flop",
        "turn",
        "river",
    }:
        clean["street"] = record["street"]
    if isinstance(record.get("street_actions"), list):
        clean["street_actions"] = [
            sanitize_round(item, player_ids, choices)
            for item in record["street_actions"]
            if isinstance(item, dict)
        ]
        # Bet is a numeric public game action, not a model response.
        for clean_item, item in zip(
            clean["street_actions"],
            (item for item in record["street_actions"] if isinstance(item, dict)),
        ):
            if _number(item.get("bet")) is not None:
                clean_item["bet"] = _number(item["bet"])
    if isinstance(record.get("result"), dict):
        clean["result"] = sanitize_round(record["result"], player_ids, choices)
    return clean


def make_event(
    session_id: str,
    event_type: str,
    payload: dict,
    *,
    player_id: str | None = None,
    round_number: int | None = None,
    agent_id: str | None = None,
    player_ids: tuple[str, ...] | list[str] = (),
) -> TelemetryEvent:
    """Build one v1 event through its allowlist; unknown event types fail closed."""
    if event_type not in EVENT_TYPES:
        raise ValueError("unknown telemetry event type")
    players = tuple(player_ids)
    if event_type == "session.created":
        clean = {
            key: payload[key]
            for key in ("arena_version", "config_hash", "game_type")
            if isinstance(payload.get(key), str)
        }
        clean["players"] = list(players)
        clean["seed"] = (
            payload.get("seed") if isinstance(payload.get("seed"), int) else None
        )
    elif event_type in {"action.accepted", "action.rejected"}:
        clean = {
            "forfeit": payload.get("forfeit") is True,
            "server_apply_ms": max(0.0, _number(payload.get("server_apply_ms")) or 0.0),
        }
        if event_type == "action.accepted":
            clean["action"] = normalize_action(payload.get("action"), players)
        else:
            clean["error_type"] = _error_type(payload.get("error_type"))
            clean["category"] = (
                payload.get("category")
                if isinstance(payload.get("category"), str)
                and payload.get("category") in ERROR_CATEGORIES
                else "invalid_action"
            )
    elif event_type == "round.completed":
        clean = {"round": sanitize_round(payload.get("round") or {}, players)}
    elif event_type == "session.completed":
        clean = {
            "total_scores": _scores(payload.get("total_scores"), players),
            "winner": _player(payload.get("winner"), players),
            "rounds_completed": max(
                0, int(_number(payload.get("rounds_completed")) or 0)
            ),
        }
    else:
        clean = {
            "error_type": _error_type(payload.get("error_type")),
            "category": "engine_error",
        }
    return TelemetryEvent(
        session_id=session_id,
        schema_version=SCHEMA_VERSION,
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        player_id=player_id,
        round_number=round_number,
        agent_id=agent_id,
        payload_json=clean,
    )


def _error_type(value: Any) -> str:
    # Exception class names only. Error messages can contain input or credentials.
    return (
        value
        if isinstance(value, str) and value.isidentifier() and len(value) <= 100
        else "reported_failure"
    )
