from arena.game_agent import GameAgent


class ExampleAgent(GameAgent):
    def act(self, history):
        raise NotImplementedError("Implement game-specific agent behavior")
