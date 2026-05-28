import secrets
import uuid
from dataclasses import dataclass, field

from blotto.config import BlottoExperimentConfig
from blotto.engine import BlottoGame, BlottoState


@dataclass
class GameSession:
    session_id: str
    config: BlottoExperimentConfig
    config_hash: str
    game: BlottoGame
    state: BlottoState
    player_tokens: dict[str, str]
    _dirty: bool = field(default=True, repr=False)

    @classmethod
    def create(cls, config):
        game = BlottoGame.from_config(config)
        player_tokens = {
            "A": secrets.token_urlsafe(32),
            "B": secrets.token_urlsafe(32),
        }

        return cls(
            session_id=str(uuid.uuid4()),
            config=config,
            config_hash=config.config_hash(),
            game=game,
            state=game.initial_state(),
            player_tokens=player_tokens,
            _dirty=True,
        )

    @classmethod
    def from_db_row(cls, row):
        from blotto.config import BattlefieldConfig

        config = BlottoExperimentConfig(
            game=row.config_json["game"],
            variant=row.config_json["variant"],
            players=row.config_json["players"],
            budget=row.config_json["budget"],
            battlefields=[
                BattlefieldConfig(id=b["id"], value=b["value"])
                for b in row.config_json["battlefields"]
            ],
            rounds=row.config_json["rounds"],
            seed=row.config_json["seed"],
        )
        game = BlottoGame.from_config(config)

        state_data = dict(row.state_json)
        state = BlottoState(
            round_number=state_data["round_number"],
            phase=state_data["phase"],
            awaiting=list(state_data["awaiting"]),
            pending_actions=dict(state_data.get("pending_actions", {})),
            history=list(state_data.get("history", [])),
            total_scores=dict(state_data.get("total_scores", {"A": 0, "B": 0})),
        )

        session = cls(
            session_id=row.id,
            config=config,
            config_hash=row.config_hash,
            game=game,
            state=state,
            player_tokens=dict(row.player_tokens_json),
            _dirty=False,
        )
        return session

    def to_db_dict(self):
        return {
            "id": self.session_id,
            "config_json": self.config.to_dict(),
            "config_hash": self.config_hash,
            "state_json": {
                "round_number": self.state.round_number,
                "phase": self.state.phase,
                "awaiting": list(self.state.awaiting),
                "pending_actions": dict(self.state.pending_actions),
                "history": list(self.state.history),
                "total_scores": dict(self.state.total_scores),
            },
            "player_tokens_json": dict(self.player_tokens),
        }

    def mark_dirty(self):
        self._dirty = True

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

    def submit_action(self, player, allocation):
        self.state = self.game.apply_action(self.state, player, allocation)
        self.mark_dirty()

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
