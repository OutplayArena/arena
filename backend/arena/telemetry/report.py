"""Read-only, versioned research summaries derived from durable telemetry.

Capture and analysis are deliberately separate: a detector receives only the
sanitized report, so new research-specific detectors need no engine changes.
Counts describe observed server events; server apply time is not model latency.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from arena.telemetry.capture import (
    ERROR_CATEGORIES,
    SCHEMA_VERSION,
    normalize_action,
    sanitize_round,
)

TERMINAL_STATUSES = frozenset({"completed", "failed"})
_CONFIG_FIELDS = frozenset(
    {
        "game",
        "variant",
        "players",
        "rounds",
        "seed",
        "battlefields",
        "budget",
        "noise",
        "scenario",
        "payoff_T",
        "payoff_R",
        "payoff_P",
        "payoff_S",
        "growth_factor",
        "initial_pot_a",
        "initial_pot_b",
        "max_steps",
        "payoff_mismatch",
        "payoff_nonpreferred",
        "payoff_preferred_a",
        "payoff_preferred_b",
        "min_offer",
        "total",
        "cost_per_unit",
        "demand_a",
        "demand_b",
        "max_quantity",
        "endowment",
        "multiplier",
        "punishment_cost",
        "punishment_effect",
        "compute_hand_equity",
        "payoff_hare_hare",
        "payoff_stag_hare",
        "payoff_stag_stag",
        "payoff_crash",
        "payoff_lose",
        "payoff_tie",
        "payoff_win",
        "max_bid",
        "truthful_tolerance",
        "value_max",
        "value_min",
    }
)
_SECRET_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
    "prompt",
    "api_key",
    "apikey",
)
PatternDetector = Callable[[Mapping[str, Any]], Iterable[dict[str, Any]]]


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _clean(value: Any) -> Any:
    """Remove credential/prompt fields recursively; retain JSON values only."""
    if isinstance(value, dict):
        return {
            str(key): _clean(item)
            for key, item in value.items()
            if isinstance(key, str)
            and not any(fragment in key.lower() for fragment in _SECRET_FRAGMENTS)
        }
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if value is None or isinstance(value, (str, bool)):
        return value
    return _number(value)


def safe_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Export known game parameters; runtime options and prompts are excluded."""
    return _clean(
        {key: value for key, value in config.items() if key in _CONFIG_FIELDS}
    )


def _scores(value: Any) -> dict[str, int | float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): number
        for key, item in value.items()
        if (number := _number(item)) is not None
    }


def safe_payload(
    event_type: str, payload: Any, player_ids: Iterable[str] = ()
) -> dict[str, Any]:
    """Defense in depth when reading historical rows, including export paths."""
    payload = payload if isinstance(payload, dict) else {}
    player_ids = tuple(player_ids)
    if event_type == "session.created":
        return {
            key: _clean(payload[key])
            for key in ("arena_version", "config_hash", "game_type", "players", "seed")
            if key in payload
        }
    if event_type in {"action.accepted", "action.rejected"}:
        result = {"forfeit": payload.get("forfeit") is True}
        latency = _number(payload.get("server_apply_ms"))
        if latency is not None and latency >= 0:
            result["server_apply_ms"] = latency
        if event_type == "action.accepted" and "action" in payload:
            result["action"] = normalize_action(payload["action"], player_ids)
        if event_type == "action.rejected":
            error_type = payload.get("error_type")
            if (
                isinstance(error_type, str)
                and error_type.isidentifier()
                and len(error_type) <= 100
            ):
                result["error_type"] = error_type
            if payload.get("category") in ERROR_CATEGORIES:
                result["category"] = payload["category"]
        return result
    if event_type == "round.completed":
        return {
            "round": sanitize_round(
                payload.get("round") if isinstance(payload.get("round"), dict) else {},
                player_ids,
            )
        }
    if event_type == "session.completed":
        result = {
            "total_scores": {
                key: value
                for key, value in _scores(payload.get("total_scores")).items()
                if key in player_ids
            }
        }
        winner = payload.get("winner")
        result["winner"] = (
            winner
            if isinstance(winner, str) and winner in {*player_ids, "Tie", "forced"}
            else None
        )
        rounds = payload.get("rounds_completed")
        if isinstance(rounds, int) and not isinstance(rounds, bool) and rounds >= 0:
            result["rounds_completed"] = rounds
        return result
    if event_type == "session.failed":
        error_type = payload.get("error_type")
        return {
            "category": "engine_error",
            "error_type": error_type
            if isinstance(error_type, str)
            and error_type.isidentifier()
            and len(error_type) <= 100
            else "reported_failure",
        }
    return {}


def event_to_dict(event: Any, player_ids: Iterable[str] = ()) -> dict[str, Any]:
    occurred_at = event.occurred_at
    return {
        "id": event.id,
        "session_id": event.session_id,
        "schema_version": event.schema_version,
        "event_type": event.event_type,
        "occurred_at": occurred_at.isoformat()
        if hasattr(occurred_at, "isoformat")
        else occurred_at,
        "player_id": event.player_id,
        "round_number": event.round_number,
        "agent_id": event.agent_id,
        "payload": safe_payload(event.event_type, event.payload_json, player_ids),
    }


def capture_coverage(report: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    if not report["coverage"]["complete"]:
        yield {
            "code": "capture_incomplete",
            "severity": "info",
            "title": "Incomplete event coverage",
            "detail": "This session does not have both creation and terminal events. Counts cover recorded events only; missing observations are not evidence of zero failures.",
            "evidence": dict(report["coverage"]),
        }


def action_rejections(report: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for player in report["players"]:
        if player["rejected_actions"]:
            yield {
                "code": "rejected_actions",
                "severity": "warning",
                "title": "Rejected action submissions",
                "player_id": player["player_id"],
                "detail": "The server rejected recorded submissions. Inspect the rejection categories in the event trace before revising the agent's action formatting or turn handling.",
                "evidence": {"rejected_actions": player["rejected_actions"]},
            }


def player_forfeits(report: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for player in report["players"]:
        if player["forfeits"]:
            yield {
                "code": "forfeits",
                "severity": "warning",
                "title": "Recorded forfeits",
                "player_id": player["player_id"],
                "detail": "Accepted submissions explicitly forfeited play. The trace records the forfeit, not its cause.",
                "evidence": {"forfeits": player["forfeits"]},
            }


def repeated_actions(report: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for player in report["players"]:
        samples = sum(item["count"] for item in player["action_distribution"])
        rate = player["repeated_action_rate"]
        if samples >= 5 and rate is not None and rate >= 0.8:
            yield {
                "code": "repeated_actions",
                "severity": "info",
                "title": "Repeated action sequence",
                "player_id": player["player_id"],
                "detail": "At least 80% of consecutive recorded non-forfeit actions were identical. Repetition may be intentional; this observation does not establish strategic quality.",
                "evidence": {
                    "sample_actions": samples,
                    "repeated_action_rate": rate,
                    "minimum_samples": 5,
                    "threshold": 0.8,
                },
            }


DEFAULT_DETECTORS: tuple[PatternDetector, ...] = (
    capture_coverage,
    action_rejections,
    player_forfeits,
    repeated_actions,
)


class ResearchReportBuilder:
    """Incrementally summarize ordered events without loading the trace in RAM.

    Add events in ascending ID order. Call finish once. A custom detector is a
    callable taking the sanitized report and yielding pattern dictionaries with
    code, severity, title, detail and evidence, plus optional player_id.
    """

    def __init__(self, row: Any):
        if row.status not in TERMINAL_STATUSES:
            raise ValueError(
                "Research telemetry is available after the session completes or fails."
            )
        self.row = row
        self.config = row.config_json or {}
        self.state = row.state_json or {}
        history = self.state.get("history", [])
        self.history = (
            [entry for entry in history if isinstance(entry, dict)]
            if isinstance(history, list)
            else []
        )
        # Built-in engines mark finalized round/hand results with total_scores.
        # Centipede has one final result after several step-history entries.
        self.finalized_rounds = sum("total_scores" in entry for entry in self.history)
        self.players: dict[str, dict[str, Any]] = {}
        self.count = 0
        self.created = False
        self.terminal = False
        self.version: str | None = None
        self.completion: dict[str, Any] = {}
        agents = row.agents_json or {}
        for player in getattr(row, "player_tokens_json", None) or {}:
            self._player(str(player))
        for player in agents:
            self._player(str(player))
        for player in _scores(self.state.get("total_scores")):
            self._player(player)

    def _player(self, player_id: str) -> dict[str, Any]:
        if player_id not in self.players:
            self.players[player_id] = {
                "player_id": player_id,
                "agent_id": (self.row.agents_json or {}).get(player_id),
                "accepted_actions": 0,
                "rejected_actions": 0,
                "forfeits": 0,
                "_latency_total": 0.0,
                "_latency_count": 0,
                "_distribution": Counter(),
                "_previous": None,
                "_repeats": 0,
                "_actions": 0,
            }
        return self.players[player_id]

    def add_event(self, event: Any) -> None:
        self.count += 1
        kind = event.event_type
        if event.player_id is not None:
            self._player(str(event.player_id))
        payload = safe_payload(kind, event.payload_json, self.players)
        if kind == "session.created":
            self.created = True
            version = payload.get("arena_version")
            if isinstance(version, str):
                self.version = version
        if kind in {"session.completed", "session.failed"}:
            self.terminal = True
        if kind == "session.completed":
            self.completion = payload
        if (
            kind not in {"action.accepted", "action.rejected"}
            or event.player_id is None
        ):
            return
        player = self._player(str(event.player_id))
        if event.agent_id:
            player["agent_id"] = event.agent_id
        if kind == "action.rejected":
            player["rejected_actions"] += 1
            return
        player["accepted_actions"] += 1
        player["forfeits"] += int(payload.get("forfeit") is True)
        latency = payload.get("server_apply_ms")
        if latency is not None:
            player["_latency_total"] += latency
            player["_latency_count"] += 1
        action = payload.get("action")
        if payload.get("forfeit") or action is None:
            return
        canonical = json.dumps(
            action,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        player["_distribution"][canonical] += 1
        if player["_actions"] and player["_previous"] == canonical:
            player["_repeats"] += 1
        player["_previous"] = canonical
        player["_actions"] += 1

    def finish(
        self, *, detectors: Iterable[PatternDetector] = DEFAULT_DETECTORS
    ) -> dict[str, Any]:
        legacy = self.count == 0
        scores = self.completion.get("total_scores") or _scores(
            self.state.get("total_scores")
        )
        winner = self.completion.get("winner")
        if winner is None and self.row.status == "completed":
            # Ask the game to apply its own winner rules; do not infer a winner
            # from scores for games whose objective may differ.
            from arena.session import GameSession

            try:
                result = GameSession.from_db_row(self.row).results()
            except (ValueError, TypeError, KeyError, AttributeError):
                result = {}
            if isinstance(result.get("winner"), str):
                winner = result["winner"]
        output_players = []
        for player_id in sorted(self.players):
            item = self.players[player_id]
            latency_count = item["_latency_count"]
            samples = item["_actions"]
            output_players.append(
                {
                    key: item[key] if not legacy else None
                    for key in ("accepted_actions", "rejected_actions", "forfeits")
                }
                | {
                    "player_id": player_id,
                    "agent_id": item["agent_id"],
                    "mean_apply_latency_ms": round(
                        item["_latency_total"] / latency_count, 6
                    )
                    if latency_count
                    else None,
                    "action_distribution": [
                        {"action": action, "count": count}
                        for action, count in sorted(item["_distribution"].items())
                    ],
                    "repeated_action_rate": round(item["_repeats"] / (samples - 1), 6)
                    if samples > 1
                    else None,
                    "score": scores.get(player_id),
                }
            )
        accepted = sum(item["accepted_actions"] for item in self.players.values())
        rejected = sum(item["rejected_actions"] for item in self.players.values())
        forfeits = sum(item["forfeits"] for item in self.players.values())
        report = {
            "schema_version": SCHEMA_VERSION,
            "session_id": self.row.id,
            "game": self.config.get("game", "unknown"),
            "status": self.row.status,
            "provenance": {
                "arena_version": self.version,
                "config_hash": self.row.config_hash,
                "seed": _clean(self.config.get("seed")),
                "config": safe_config(self.config),
                "agents": {
                    item["player_id"]: item["agent_id"]
                    for item in output_players
                    if item["agent_id"] is not None
                },
            },
            "coverage": {
                "event_count": self.count,
                "recorded_actions": accepted,
                "history_rounds": self.finalized_rounds,
                "history_entries": len(self.history),
                "legacy": legacy,
                "complete": self.created and self.terminal,
                "action_source": "unavailable" if legacy else "events",
            },
            "summary": {
                "rounds_completed": self.completion.get(
                    "rounds_completed", self.finalized_rounds
                ),
                "action_count": None if legacy else accepted,
                "rejected_actions": None if legacy else rejected,
                "forfeits": None if legacy else forfeits,
                "scores": scores,
                "winner": winner,
            },
            "players": output_players,
            "patterns": [],
        }
        for detector in detectors:
            report["patterns"].extend(detector(report))
        return report


def build_report(
    row: Any,
    events: Iterable[Any] = (),
    *,
    detectors: Iterable[PatternDetector] = DEFAULT_DETECTORS,
) -> dict[str, Any]:
    """Build a deterministic report; pass detectors to extend or replace defaults."""
    builder = ResearchReportBuilder(row)
    for event in events:
        builder.add_event(event)
    return builder.finish(detectors=detectors)
