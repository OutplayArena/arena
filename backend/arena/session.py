from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arena._version import ARENA_VERSION
from arena.game_engine import GameEngine
from arena.game_registry import GameRegistry
from arena.metrics.contracts import Match, Move
from arena.models.session import SessionModel
from arena.auth.session_key import derive_session_key, validate_session_key
from arena.metrics import get_global_registry, MatchEvaluator


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

    @classmethod
    def create(
        cls,
        config,
        game=None,
        locked: bool = False,
        agents: dict[str, str] | None = None,
    ) -> "GameSession":
        if game is None:
            game = GameRegistry().game_from_config(config)

        session_id = str(uuid.uuid4())
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
        )
        db.add(row)
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

    def submit_action(self, player, allocation):
        self.state = self.game.apply_action(self.state, player, allocation)
        self._update_status_from_state()

    def _update_status_from_state(self):
        state_dict = _serialize_state(self.state)
        phase = state_dict.get("phase", "")
        if phase == "complete":
            self.status = "completed"
        elif state_dict.get("round_number", 1) > 1 or len(state_dict.get("history", [])) > 0:
            self.status = "running"

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.error_message = error

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
        for entry in history:
            round_num = entry.get("round", 0)
            actions = entry.get("allocations") or entry.get("actions", {})
            scores = entry.get("payoffs") or entry.get("scores", {})

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
        state_dict = _serialize_state(self.state)
        phase = state_dict.get("phase", "")
        if phase == "complete":
            raise ValueError("game already complete")
        player = self.player_for_token(token)
        if forfeit:
            self.state = self.game.forfeit_round(self.state, player)
            self._update_status_from_state()
        else:
            self.submit_action(player, allocation)

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
            scores = entry.get("scores", {})
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
