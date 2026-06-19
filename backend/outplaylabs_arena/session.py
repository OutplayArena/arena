from dataclasses import dataclass, asdict, is_dataclass
from typing import Any
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from outplaylabs_arena.experiment_config import ExperimentRuntimeConfig
from outplaylabs_arena.game_engine import GameEngine
from outplaylabs_arena.game_registry import GameRegistry
from outplaylabs_arena.integrations.wandb_logger import WandbGameLogger, encrypt_api_key
from outplaylabs_arena.metrics.contracts import Match, Move
from outplaylabs_arena.models.session import SessionModel
from outplaylabs_arena.auth.session_key import derive_session_key, validate_session_key
from outplaylabs_arena.metrics import get_global_registry, MatchEvaluator


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
    runtime_config: ExperimentRuntimeConfig | None = None
    wandb_logger: WandbGameLogger | None = None
    wandb_finished: bool = False

    @classmethod
    def create(cls, config, game=None, locked: bool = False, runtime_config=None) -> "GameSession":
        if game is None:
            game = GameRegistry().game_from_config(config)
        if runtime_config is None:
            runtime_config = ExperimentRuntimeConfig()
        # Start optional W&B logging before exposing player tokens.
        if runtime_config.wandb:
            encrypted_key = encrypt_api_key(runtime_config.wandb.api_key)
            wandb_logger = WandbGameLogger(
                wandb_config=runtime_config.wandb,
                game_config=config,
                encrypted_api_key=encrypted_key,
            ).start()
        else:
            wandb_logger = None
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
            runtime_config=runtime_config,
            wandb_logger=wandb_logger,
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
        )

    async def save_new(self, db: AsyncSession, user_id: str | None = None, agents: dict[str, str] | None = None) -> None:
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
        return result

    def add_message(self, sender: str, content: str, recipient: str = "all") -> dict:
        """Add a mailbox message to the session."""
        if self.messages is None:
            self.messages = []
        
        state_dict = _serialize_state(self.state)
        round_number = state_dict.get("round_number", 0)
        
        msg = {
            "id": str(uuid.uuid4()),
            "sender": sender,
            "recipient": recipient,
            "content": content,
            "round": round_number,
        }
        self.messages.append(msg)
        return msg

    def submit_action(self, player, allocation):
        before_history_len = len(self.state.history)
        self.state = self.game.apply_action(self.state, player, allocation)
        self._update_status_from_state()
        after_history_len = len(self.state.history)
        if after_history_len > before_history_len:
            self._log_latest_round_to_wandb()
            if self.game.is_terminal(self.state):
                self._log_terminal_to_wandb()

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
        player_ids = list(self.config.player_ids()) if hasattr(self.config, "player_ids") else ["A", "B"]

        moves = []
        for entry in history:
            round_num = entry.get("round", 0)
            actions = entry.get("allocations") or entry.get("actions", {})
            scores = entry.get("payoffs") or entry.get("scores", {})

            for player in player_ids:
                action = actions.get(player)
                payoff = float(scores.get(player, 0))
                if action is not None:
                    moves.append(Move(
                        agent_id=player,
                        round_number=round_num,
                        action=action,
                        payoff=payoff,
                    ))

        return Match(
            match_id=self.session_id,
            game_type=game_type,
            agent_ids=player_ids,
            moves=moves,
            config=config_dict,
        )

    def creation_response(self):
        return {
            "session_id": self.session_id,
            "config_hash": self.config_hash,
            "player_tokens": dict(self.player_tokens),
        }

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

    def _log_latest_round_to_wandb(self):
        if self.wandb_logger is None:
            return
        if not self.state.history:
            return

        latest = self.state.history[-1]
        step = latest["round"]

        payload = {
            "round": latest["round"],
            "winner": latest["winner"],
        }

        scores = latest.get("scores", {})
        total_scores = latest.get("total_scores", {})
        for player in scores:
            payload[f"scores/{player}"] = scores[player]
            payload[f"total_scores/{player}"] = total_scores.get(player, 0)

        allocations = latest.get("allocations", {})
        for player, allocation in allocations.items():
            if isinstance(allocation, list):
                total = sum(allocation)
                concentration = 0 if total == 0 else max(allocation) / total
                payload[f"allocation_concentration/{player}"] = concentration

        self.wandb_logger.log_round(payload, step=step)

    def _log_terminal_to_wandb(self):
        if self.wandb_logger is None or self.wandb_finished:
            return

        evaluator = MatchEvaluator(get_global_registry())
        results = self.results(evaluator=evaluator)
        metrics = results.get("metrics", {})
        total_scores = results.get("total_scores", {})

        payload: dict[str, object] = {
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

        self.wandb_logger.log_terminal(payload)
        self.wandb_logger.finish()
        self.wandb_finished = True
