# POST /api/game/experiment or /api/frontend/experiment
#   -> GameSession.create(config)

# GET /api/game/session/{id}/state or /api/frontend/session/{id}/state
#   -> session.public_state()

# POST /api/game/session/{id}/action or /api/frontend/session/{id}/action
#   -> session.submit_action(player, allocation)

# GET /api/game/session/{id}/results or /api/frontend/session/{id}/results
#   -> session.results()

from dataclasses import dataclass
from typing import Any
import uuid

from nash_arena.auth import AuthError, create_player_token, decode_player_token
from nash_arena.experiment_config import ExperimentRuntimeConfig
from nash_arena.game_engine import GameEngine
from nash_arena.game_registry import GameRegistry

@dataclass
class GameSession: 
    session_id: str
    config: Any
    config_hash: str
    game: GameEngine
    state: Any
    player_tokens: dict[str, str]
    runtime_config: ExperimentRuntimeConfig
    
    # Future POST /api/game/experiment behavior minus HTTP
    @classmethod
    def create(cls, config, game=None, runtime_config=None):
        if game is None:
            game = GameRegistry().game_from_config(config)
        if runtime_config is None:
            runtime_config = ExperimentRuntimeConfig()
        session_id = str(uuid.uuid4())
        player_tokens = {
            player: create_player_token(session_id=session_id, player=player)
            for player in config.player_ids()
        }
        
        return cls(
            session_id=session_id,
            config=config,
            config_hash=config.config_hash(),
            game=game,
            state=game.initial_state(),
            player_tokens=player_tokens,
            runtime_config=runtime_config,
        )
        
    # Equivalent of: GET /api/game/session/{id}/state
    # What external agents will see
    def public_state(self):
        return self.game.public_state(
            state=self.state,
            config=self.config,
            session_id=self.session_id,
            config_hash=self.config_hash,
        )
        
    # Equivalent of: POST /api/game/session/{id}/action
    def submit_action(self, player, allocation):
        self.state = self.game.apply_action(self.state, player, allocation)
        
    # Equivalent of: GET /api/game/session/{id}/results
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
        
    # Resolve the player identity encoded in a signed session token.
    def player_for_token(self, token):
        try:
            claims = decode_player_token(token, session_id=self.session_id)
        except AuthError as exc:
            raise ValueError("invalid player token") from exc

        player = claims.get("player")
        if player not in self.config.player_ids():
            raise ValueError("invalid player token")
        return player
    
    # Submit an action using the player identity encoded in the token.
    def submit_action_with_token(self, token, allocation):
        player = self.player_for_token(token)
        self.submit_action(player, allocation)
        
