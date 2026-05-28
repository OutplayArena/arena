# POST /experiment
#   -> GameSession.create(config)

# GET /session/{id}/state
#   -> session.public_state()

# POST /session/{id}/action
#   -> session.submit_action(player, allocation)

# GET /session/{id}/results
#   -> session.results()

from dataclasses import dataclass
from typing import Any
import secrets
import uuid

from arena.game_engine import GameEngine
from arena.game_registry import GameRegistry

@dataclass
class GameSession: 
    session_id: str
    config: Any
    config_hash: str
    game: GameEngine
    state: Any
    player_tokens: dict[str, str]
    
    # Future POST /experiment behavior minus HTTP
    @classmethod
    def create(cls, config, game=None):
        if game is None:
            game = GameRegistry().game_from_config(config)
        player_tokens = {
            player: secrets.token_urlsafe(32)
            for player in config.player_ids()
        }
        
        return cls(
            session_id=str(uuid.uuid4()),
            config=config,
            config_hash=config.config_hash(),
            game=game,
            state=game.initial_state(),
            player_tokens=player_tokens,
        )
        
    # Equivalent of: GET /session/{id}/state
    # What external agents will see
    def public_state(self):
        return self.game.public_state(
            state=self.state,
            config=self.config,
            session_id=self.session_id,
            config_hash=self.config_hash,
        )
        
    # Equivalent of: POST /session/{id}/action
    def submit_action(self, player, allocation):
        self.state = self.game.apply_action(self.state, player, allocation)
        
    # Equivalent of: GET /session/{id}/results
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
        for player, player_token in self.player_tokens.items():
            if secrets.compare_digest(token, player_token):
                return player
            
        raise ValueError("invalid player token")
    
    def submit_action_with_token(self, token, allocation):
        player = self.player_for_token(token)
        self.submit_action(player, allocation)
        
