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
from nash_arena.integrations.wandb_logger import WandbGameLogger, encrypt_api_key

@dataclass
class GameSession: 
    session_id: str
    config: Any
    config_hash: str
    game: GameEngine
    state: Any
    player_tokens: dict[str, str]
    runtime_config: ExperimentRuntimeConfig
    wandb_logger: WandbGameLogger | None = None
    wandb_finished: bool = False
    
    # Future POST /api/game/experiment behavior minus HTTP
    @classmethod
    def create(cls, config, game=None, runtime_config=None):
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
            wandb_logger=wandb_logger,
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
        before_history_len = len(self.state.history)
        self.state = self.game.apply_action(self.state, player, allocation)
        after_history_len = len(self.state.history)

        if after_history_len > before_history_len:
            self._log_latest_round_to_wandb()
            if self.game.is_terminal(self.state):
                self._log_terminal_to_wandb()
        
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
        
    # Log the latest completed round to W&B when optional logging is enabled.
    def _log_latest_round_to_wandb(self):
        if self.wandb_logger is None:
            return
        if not self.state.history:
            return

        latest = self.state.history[-1]
        step = latest["round"]

        payload = {
            "round": latest["round"],
            "scores/A": latest["scores"]["A"],
            "scores/B": latest["scores"]["B"],
            "total_scores/A": latest["total_scores"]["A"],
            "total_scores/B": latest["total_scores"]["B"],
            "winner": latest["winner"],
        }

        allocations = latest.get("allocations", {})
        for player, allocation in allocations.items():
            total = sum(allocation)
            concentration = 0 if total == 0 else max(allocation) / total
            payload[f"allocation_concentration/{player}"] = concentration

        self.wandb_logger.log_round(payload, step=step)
    # Log final W&B metrics and finish the run once the game is terminal.
    def _log_terminal_to_wandb(self):
        if self.wandb_logger is None or self.wandb_finished:
            return

        results = self.results()
        metrics = results.get("metrics", {})
        total_scores = results.get("total_scores", {})

        payload = {
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

        self.wandb_logger.log_terminal(payload)
        self.wandb_logger.finish()
        self.wandb_finished = True
