from dataclasses import dataclass, asdict, is_dataclass
from typing import Any
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from nash_arena.game_engine import GameEngine
from nash_arena.game_registry import GameRegistry
from nash_arena.models.session import SessionModel
from nash_arena.auth.session_key import derive_session_key, validate_session_key


def _serialize_state(state: Any) -> dict:
    if is_dataclass(state) and not isinstance(state, type):
        return asdict(state)
    if isinstance(state, dict):
        return state
    if hasattr(state, "to_dict"):
        return state.to_dict()
    return state


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

    @classmethod
    def create(cls, config, game=None, locked: bool = False) -> "GameSession":
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
        return self.game.public_state(
            state=self.state,
            config=self.config,
            session_id=self.session_id,
            config_hash=self.config_hash,
        )

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

    def results(self):
        return self.game.compute_results(
            state=self.state,
            session_id=self.session_id,
            config_hash=self.config_hash,
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
