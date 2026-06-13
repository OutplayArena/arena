from nash_arena.game_components.game_metrics import GameMetrics


class ExampleMetrics(GameMetrics):
    def compute(self, history, total_scores):
        raise NotImplementedError("Implement game-specific metrics")
