from copy import deepcopy
from dataclasses import dataclass, asdict, field, is_dataclass
from time import perf_counter
from datetime import datetime, timezone
from typing import Any
import logging
import secrets
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from arena._version import ARENA_VERSION
from arena.auth.session_key import derive_session_key, validate_session_key
from arena.game_engine import GameEngine
from arena.game_registry import GameRegistry
from arena.metrics import MatchEvaluator, get_global_registry
from arena.metrics.contracts import Match, Move
from arena.models.session import SessionModel
from arena.auth.session_key import derive_session_key, validate_session_key
from arena.metrics import get_global_registry, MatchEvaluator
from arena.models.telemetry_event import TelemetryEvent
from arena.telemetry.capture import make_event, normalize_action, sanitize_round


def _serialize_state(state: Any) -> dict:
    if is_dataclass(state) and not isinstance(state, type):
        return asdict(state)
    if isinstance(state, dict):
        return state
    if hasattr(state, "to_dict"):
        return state.to_dict()
    return state


def _round_metrics(obj: Any, decimals: int = 4) -> Any:
    if isinstance(obj, float):
        return round(obj, decimals)
    if isinstance(obj, dict):
        return {k: _round_metrics(v, decimals) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_metrics(v, decimals) for v in obj]
    return obj

@dataclass
class GameSession:
    session_id: str
    config: Any
    config_hash: str
    game: GameEngine
    state: Any
    player_tokens: dict[str, str]
    status: str = "ready"
    error_message: str | None = None
    locked: bool = False
    agents: dict[str, str] | None = None
    messages: list[dict] | None = None
    wandb_run_meta: dict | None = None
    _pending_telemetry: list[TelemetryEvent] = field(default_factory=list, init=False, repr=False)
    _telemetry_creation_recorded: bool = field(default=False, init=False, repr=False)

    @classmethod
    def create(
        cls,
        config,
        game=None,
        locked: bool = False,
        agents: dict[str, str] | None = None,
        session_id: str | None = None,
    ) -> "GameSession":
        if game is None:
            game = GameRegistry().game_from_config(config)

        session_id = session_id or str(uuid.uuid4())
        player_tokens = {
            player: derive_session_key(session_id, player)
            for player in config.player_ids()
        }
        state = game.initial_state()
        return cls(
            session_id=session_id,
            config=config,
            config_hash=config.config_hash(),
            game=game,
            state=state,
            player_tokens=player_tokens,
            status="ready",
            locked=locked,
            agents=agents,
        )

    @classmethod
    def from_db_row(cls, row: SessionModel) -> "GameSession":
        registry = GameRegistry()
        config = registry.config_from_request(row.config_json)
        game = registry.game_from_config(config)
        state = row.state_json
        if isinstance(state, dict):
            state = game.state_from_dict(state) if hasattr(game, "state_from_dict") else state
        return cls(
            session_id=row.id,
            config=config,
            config_hash=row.config_hash,
            game=game,
            state=state,
            player_tokens=row.player_tokens_json,
            status=row.status,
            error_message=row.error_message,
            locked=row.locked,
            agents=row.agents_json,
            messages=row.messages_json,
            wandb_run_meta=row.wandb_run_json,
        )

    async def save_new(
        self,
        db: AsyncSession,
        user_id: str | None = None,
        agents: dict[str, str] | None = None,
        wandb_config_json: dict | None = None,
        match_id: str | None = None,
    ) -> None:
        row = SessionModel(
            id=self.session_id,
            config_json=self.config.to_dict(),
            config_hash=self.config_hash,
            state_json=_serialize_state(self.state),
            player_tokens_json=self.player_tokens,
            user_id=user_id,
            agents_json=agents,
            status=self.status,
            error_message=self.error_message,
            locked=self.locked,
            messages_json=self.messages or [],
            wandb_config_json=wandb_config_json,
            match_id=match_id,
        )
        db.add(row)
        await db.flush()  # The parent session must exist before FK event inserts.
        if agents is not None:
            self.agents = agents
        if not self._telemetry_creation_recorded:
            config = self.config.to_dict()
            created = make_event(self.session_id, "session.created", {
                "arena_version": ARENA_VERSION, "config_hash": self.config_hash,
                "game_type": config.get("game", "unknown"), "seed": config.get("seed"),
            }, player_ids=self._telemetry_players())
            self._pending_telemetry.insert(0, created)
            self._telemetry_creation_recorded = True
        await self.flush_telemetry(db)
        await db.commit()

    async def save_state(self, db: AsyncSession) -> None:
        from sqlalchemy import select
        result = await db.execute(select(SessionModel).where(SessionModel.id == self.session_id))
        row = result.scalar_one_or_none()
        if row:
            row.state_json = _serialize_state(self.state)
            row.player_tokens_json = self.player_tokens
            row.status = self.status
            row.error_message = self.error_message
            row.locked = self.locked
            await self.flush_telemetry(db)
            await db.commit()

    def public_state(self):
        result = self.game.public_state(
            state=self.state,
            config=self.config,
            session_id=self.session_id,
            config_hash=self.config_hash,
        )
        result["messages"] = self.messages or []
        if self.wandb_run_meta:
            result["wandb_run"] = self.wandb_run_meta
        return result

    def add_message(self, sender: str, content: str, recipient: str = "all") -> dict:
        """Add a mailbox message to the session."""
        if self.messages is None:
            self.messages = []

        state_dict = _serialize_state(self.state)
        round_number = state_dict.get("round_number", 0)
        turn_phase = "before" if sender in state_dict.get("awaiting", []) else "after"

        msg = {
            "id": str(uuid.uuid4()),
            "sender": sender,
            "recipient": recipient,
            "content": content,
            "round": round_number,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "turn_phase": turn_phase,
        }
        self.messages.append(msg)
        return msg

    def _telemetry_players(self) -> tuple[str, ...]:
        return tuple(self.config.player_ids())

    def _telemetry_choices(self) -> dict[str, str]:
        # Configurable labels are represented by stable game choices, not text.
        if hasattr(self.game, "option_a") and hasattr(self.game, "option_b"):
            return {self.game.option_a: "option_a", self.game.option_b: "option_b"}
        return {}

    def _record_event(self, event_type: str, payload: dict, *, player=None, round_number=None):
        self._pending_telemetry.append(make_event(
            self.session_id, event_type, payload,
            player_id=player, round_number=round_number,
            agent_id=(self.agents or {}).get(player) if player is not None else None,
            player_ids=self._telemetry_players(),
        ))

    async def flush_telemetry(self, db: AsyncSession) -> None:
        """Insert pending events in the caller's state transaction, never commit.

        The caller must roll back both state and events if persistence fails.
        Keeping the buffer until flush succeeds also permits retrying a failed
        flush without silently forgetting events.
        """
        pending = list(self._pending_telemetry)
        if not pending:
            return
        for event in pending:
            db.add(event)
        await db.flush()
        del self._pending_telemetry[:len(pending)]

    def record_rejection(
        self, player: str, error: Exception, *, forfeit: bool = False,
        server_apply_ms: float = 0.0,
    ) -> None:
        """Record validated-player failures; never call for authentication errors."""
        if player not in self._telemetry_players():
            return
        state = _serialize_state(self.state)
        awaiting = state.get("awaiting", [state.get("current_player")])
        if self.status == "failed":
            category = "session_failed"
        elif self.status == "completed" or state.get("phase") == "complete":
            category = "session_complete"
        elif player not in awaiting:
            category = "out_of_turn"
        elif isinstance(error, NotImplementedError):
            category = "unsupported_action"
        elif isinstance(error, ValueError):
            category = "invalid_action"
        else:
            category = "engine_error"
        self._record_event("action.rejected", {
            "error_type": type(error).__name__, "category": category,
            "forfeit": forfeit, "server_apply_ms": server_apply_ms,
        }, player=player, round_number=state.get("round_number", state.get("hand_number", 1)))

    def _apply_recorded_action(self, player, allocation, *, forfeit: bool = False):
        # Copy history before applying: some games resolve by updating an existing
        # history entry (public-goods punishment), rather than appending one.
        before = deepcopy(_serialize_state(self.state))
        previous_status = self.status
        started = perf_counter()
        try:
            if self.status == "failed":
                raise ValueError("session already failed")
            if self.status == "completed" or before.get("phase") == "complete":
                raise ValueError("game already complete")
            if forfeit:
                self.state = self.game.forfeit_round(self.state, player)
            else:
                self.state = self.game.apply_action(self.state, player, allocation)
        except Exception as exc:
            self.record_rejection(
                player, exc, forfeit=forfeit,
                server_apply_ms=(perf_counter() - started) * 1000,
            )
            raise
        server_apply_ms = (perf_counter() - started) * 1000
        self._update_status_from_state()
        after = _serialize_state(self.state)
        round_number = before.get("round_number", before.get("hand_number", 1))
        self._record_event("action.accepted", {
            "action": None if forfeit else normalize_action(
                allocation, self._telemetry_players(), self._telemetry_choices()
            ),
            "forfeit": forfeit, "server_apply_ms": server_apply_ms,
        }, player=player, round_number=round_number)
        old_history = before.get("history", [])
        history = after.get("history", [])
        for index, entry in enumerate(history):
            # In the built-in game contract total_scores marks final resolution.
            # Interim contribution records / centipede steps are not full rounds.
            if not isinstance(entry, dict) or "total_scores" not in entry:
                continue
            old_entry = old_history[index] if index < len(old_history) else None
            if isinstance(old_entry, dict) and "total_scores" in old_entry:
                continue
            resolved = sanitize_round(entry, self._telemetry_players(), self._telemetry_choices())
            number = entry.get("round", entry.get("hand", round_number))
            self._record_event("round.completed", {"round": resolved}, round_number=number)
        if self.status == "completed" and previous_status != "completed":
            scores = after.get("total_scores") or {}
            # Use the engine winner; do not invoke optional model evaluators.
            winner = None
            try:
                # Engine results know game-specific tie and winner semantics.
                # Read only the winner; no metrics or arbitrary result text is stored.
                result = self.game.compute_results(self.state)
                if isinstance(result, dict):
                    winner = result.get("winner")
            except Exception:  # noqa: BLE001 - telemetry cannot invalidate a successful game
                logging.getLogger(__name__).warning(
                    "Winner unavailable for completed telemetry session %s", self.session_id
                )
            self._record_event("session.completed", {
                "total_scores": scores,
                "winner": winner,
                "rounds_completed": sum(
                    isinstance(entry, dict) and "total_scores" in entry for entry in history
                ),
            }, round_number=after.get("round_number", round_number))

    def submit_action(self, player, allocation):
        self._apply_recorded_action(player, allocation)

    def _update_status_from_state(self):
        state_dict = _serialize_state(self.state)
        phase = state_dict.get("phase", "")
        if phase == "complete":
            self.status = "completed"
        elif state_dict.get("round_number", 1) > 1 or len(state_dict.get("history", [])) > 0:
            self.status = "running"

    def mark_failed(self, error: str | Exception) -> None:
        previous_status = self.status
        self.status = "failed"
        self.error_message = str(error)
        if previous_status != "failed":
            self._record_event("session.failed", {
                "error_type": type(error).__name__ if isinstance(error, Exception) else "reported_failure",
            })

    def results(self, evaluator=None):
        result = self.game.compute_results(
            state=self.state,
            session_id=self.session_id,
            config_hash=self.config_hash,
        )
        result["metrics"] = _round_metrics(result.get("metrics", {}))
        if evaluator is not None:
            match = self.to_match()
            registry = GameRegistry()
            game_type = match.game_type
            extension = registry.metrics_extension(game_type)
            declared = registry.get_metric_names(game_type)
            config_dict = self.config.to_dict() if hasattr(self.config, "to_dict") else {}
            rich = evaluator.evaluate(match, extension=extension, game_config=config_dict, declared_metrics=declared)
            result["rich_metrics"] = _round_metrics(rich)
        return result

    def to_match(self) -> Match:
        state_dict = _serialize_state(self.state)
        history = state_dict.get("history", [])
        config_dict = self.config.to_dict() if hasattr(self.config, "to_dict") else {}
        game_type = config_dict.get("game", "unknown")
        role_ids = list(self.config.player_ids()) if hasattr(self.config, "player_ids") else ["A", "B"]

        # Resolve role labels ("A", "B") to actual model/agent names from
        # agents_json so the leaderboard tracks real identifiers, not generic roles.
        # Falls back to the role ID when agents_json is absent or incomplete.
        agents = self.agents or {}
        agent_names = {role: (agents.get(role) or role) for role in role_ids}

        moves = []
        # Cumulative total_scores from the previous hand, for games (Texas
        # Hold'em) that record a running total rather than a per-round delta.
        prev_total_scores: dict[str, float] = {role: 0.0 for role in role_ids}
        for entry in history:
            round_num = entry.get("round", entry.get("hand", 0))

            if "street_actions" in entry:
                # Multi-street-per-round games (Texas Hold'em) don't record a
                # single actions/scores dict per round: they record a list of
                # per-street actions and a *cumulative* total_scores (#24).
                # Derive one representative action per player (their last
                # recorded action this hand) and a payoff equal to this hand's
                # total_scores delta.
                last_action: dict[str, Any] = {}
                for act in entry.get("street_actions", []):
                    p = act.get("player")
                    if p is not None:
                        last_action[p] = act.get("action")
                total_scores = entry.get("total_scores") or {}
                for role in role_ids:
                    action = last_action.get(role)
                    if action is None:
                        continue
                    cur_total = float(total_scores.get(role, prev_total_scores[role]))
                    moves.append(Move(
                        agent_id=agent_names[role],
                        round_number=round_num,
                        action=action,
                        payoff=cur_total - prev_total_scores[role],
                    ))
                prev_total_scores = {
                    role: float(total_scores.get(role, prev_total_scores[role]))
                    for role in role_ids
                }
                continue

            actions = entry.get("allocations") or entry.get("actions", {})
            scores = entry.get("payoffs") or entry.get("scores") or entry.get("round_payoffs", {})

            for role in role_ids:
                action = actions.get(role)
                payoff = float(scores.get(role, 0))
                if action is not None:
                    moves.append(Move(
                        agent_id=agent_names[role],
                        round_number=round_num,
                        action=action,
                        payoff=payoff,
                    ))

        return Match(
            match_id=self.session_id,
            game_type=game_type,
            agent_ids=list(agent_names.values()),
            moves=moves,
            config=config_dict,
        )

    def creation_response(self):
        resp = {
            "session_id": self.session_id,
            "arena_version": ARENA_VERSION,
            "config_hash": self.config_hash,
            "config": self.config.to_dict() if hasattr(self.config, "to_dict") else {},
            "player_tokens": dict(self.player_tokens),
            "status": self.status,
        }
        if self.wandb_run_meta:
            resp["wandb_run"] = self.wandb_run_meta
        return resp

    def player_for_token(self, token):
        try:
            session_id, player = validate_session_key(token)
            if session_id != self.session_id:
                raise ValueError("invalid player token")
            return player
        except ValueError:
            pass

        for player, player_token in self.player_tokens.items():
            if secrets.compare_digest(token, player_token):
                return player

        raise ValueError("invalid player token")

    def submit_action_with_token(self, token, allocation, forfeit: bool = False):
        # Authenticate first so invalid tokens never create research events.
        player = self.player_for_token(token)
        self._apply_recorded_action(player, allocation, forfeit=forfeit)

    def build_wandb_round_payloads(self) -> list[tuple[dict[str, Any], int]]:
        """Return (payload, step) for each resolved round in the session history."""
        payloads = []
        history = self.state.history if hasattr(self.state, "history") else _serialize_state(self.state).get("history", [])
        for entry in history:
            step = entry.get("round") or entry.get("hand") or 0
            payload: dict[str, Any] = {
                "round": step,
                "winner": entry.get("winner"),
            }
            scores = entry.get("payoffs") or entry.get("scores") or entry.get("round_payoffs", {})
            total_scores = entry.get("total_scores", {})
            for player in scores:
                payload[f"scores/{player}"] = scores[player]
                payload[f"total_scores/{player}"] = total_scores.get(player, 0)
            allocations = entry.get("allocations", {})
            for player, allocation in allocations.items():
                if isinstance(allocation, list):
                    total = sum(allocation)
                    concentration = 0 if total == 0 else max(allocation) / total
                    payload[f"allocation_concentration/{player}"] = concentration
            payloads.append((payload, step))
        return payloads

    def build_wandb_terminal_payload(self) -> dict[str, Any]:
        """Return the flat W&B payload for terminal/summary metrics."""
        evaluator = MatchEvaluator(get_global_registry())
        results = self.results(evaluator=evaluator)
        metrics = results.get("metrics", {})
        total_scores = results.get("total_scores", {})

        payload: dict[str, Any] = {
            "final/winner": results.get("winner"),
        }

        for player, score in total_scores.items():
            payload[f"final/total_scores/{player}"] = score

        average_payoff = metrics.get("average_payoff", {})
        for player, value in average_payoff.items():
            payload[f"metrics/average_payoff/{player}"] = value

        round_win_rate = metrics.get("round_win_rate", {})
        for player, value in round_win_rate.items():
            payload[f"metrics/round_win_rate/{player}"] = value

        rich = results.get("rich_metrics", {})
        for agent_id, agent_data in rich.get("agents", {}).items():
            for key, value in agent_data.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, (int, float)):
                            payload[f"rich/{agent_id}/{key}/{sub_key}"] = sub_value
                elif isinstance(value, (int, float)):
                    payload[f"rich/{agent_id}/{key}"] = value

        for key, value in rich.get("joint", {}).items():
            if isinstance(value, (int, float)):
                payload[f"rich/joint/{key}"] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, (int, float)):
                        payload[f"rich/joint/{key}/{sub_key}"] = sub_value

        for key, value in rich.get("pairwise", {}).items():
            if isinstance(value, (int, float)):
                payload[f"rich/pairwise/{key}"] = value

        return payload
