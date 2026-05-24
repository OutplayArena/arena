# POST /experiment
#   -> GameSession.create(config)

# GET /session/{id}/state
#   -> session.public_state()

# POST /session/{id}/action
#   -> session.submit_action(player, allocation)

# GET /session/{id}/results
#   -> session.results()

from dataclasses import dataclass
import uuid

from blotto.api import BlottoGame, BlottoState
from blotto.config import BlottoExperimentConfig 

@dataclass
class GameSession: 
    session_id: str
    config: BlottoExperimentConfig
    config_hash: str
    game: BlottoGame
    state: BlottoState
    
    # Future POST /experiment behavior minus HTTP
    @classmethod
    def create(cls, config):
        game = BlottoGame.from_config(config)
        
        return cls(
            session_id=str(uuid.uuid4()),
            config=config,
            config_hash=config.config_hash(),
            game=game,
            state=game.initial_state()
        )
        
    # Equivalent of: GET /session/{id}/state
    # What external agents will see
    def public_state(self):
        return {
            "session_id": self.session_id,
            "config_hash": self.config_hash,
            "round": self.state.round_number,
            "round_total": self.config.rounds,
            "phase": self.state.phase,
            "awaiting": list(self.state.awaiting),
            "battlefields": [
                {"id": b.id, "value": b.value}
                for b in self.config.battlefields
            ],
            "budgets": {"A": self.config.budget[0], "B": self.config.budget[1]},
            "total_scores": dict(self.state.total_scores),
            "history": list(self.state.history),
        }
        
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
