"""
NashArena Benchmark Runner

Runs a round-robin tournament between specified rule-based agents on one or
more games, aggregates metrics, and prints a leaderboard.

Usage examples:
  python run_benchmark.py --games prisonersdilemma stag_hunt --agents all --n-games 20
  python run_benchmark.py --games rock_paper_scissors --agents random nash --n-games 50
  python run_benchmark.py --games centipede ultimatum --agents all --n-games 10 --seed 42

Output:
  - Per-game metric summary for each agent
  - Overall Elo leaderboard
  - α-Rank leaderboard (evolutionary dominance)
  - Benchmark dimension scores (competitive / cooperative / adaptive / cognitive)
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nash_arena.game_registry import GameRegistry, GameRegistryError
from nash_arena.metrics import AgentRegistry, MatchEvaluator
from nash_arena.metrics.contracts import Match, Move
from nash_arena.metrics.benchmark import BenchmarkReport
from dataclasses import asdict, is_dataclass


REGISTRY = GameRegistry()

# ── Agent factories per game ───────────────────────────────────────────────────


def _get_agent_classes(game_slug: str) -> dict[str, Any]:
    """Return a dict of agent_id -> agent_class for a game's built-in agents."""
    import importlib
    import inspect
    try:
        game_dir = REGISTRY._game_dir(game_slug)
        namespace = game_dir.parent.name
        module = importlib.import_module(f"games.{namespace}.{game_slug}.agent")
        classes = {}
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and name[0].isupper()
                    and not inspect.isabstract(obj)
                    and obj.__module__ == module.__name__):
                classes[name] = obj
        return classes
    except Exception:
        return {}


def _build_agent(game_slug: str, agent_spec: str, config, player: str = "A"):
    """Instantiate an agent by spec string (class name or alias)."""
    classes = _get_agent_classes(game_slug)
    # Try direct class name first
    cls = classes.get(agent_spec)
    if cls is None:
        # Try case-insensitive
        for k, v in classes.items():
            if k.lower() == agent_spec.lower():
                cls = v
                break
    if cls is None:
        raise ValueError(f"Unknown agent {agent_spec!r} for game {game_slug!r}. "
                         f"Available: {list(classes.keys())}")
    # Try to pass common config params
    try:
        return cls()
    except TypeError:
        pass
    # Try player parameter
    try:
        return cls(player=player)
    except TypeError:
        pass
    return cls.__new__(cls)


# ── Game runner ────────────────────────────────────────────────────────────────


def _serialize(state: Any) -> dict:
    if is_dataclass(state) and not isinstance(state, type):
        return asdict(state)
    if isinstance(state, dict):
        return state
    if hasattr(state, "to_dict"):
        return state.to_dict()
    return state


def play_match(game_slug: str, agent_a_spec: str, agent_b_spec: str,
               config, seed_offset: int = 0) -> dict | None:
    """
    Play a single match between two rule-based agents.
    Returns the rich_metrics dict or None on error.
    """
    import random

    game = REGISTRY.game_from_config(config)
    # Re-seed if the game has an rng
    if hasattr(game, "_rng") and seed_offset:
        game._rng = random.Random(seed_offset)

    player_ids = list(config.player_ids())

    # Build agents
    try:
        agent_a = _build_agent(game_slug, agent_a_spec, config, player=player_ids[0])
        agent_b = _build_agent(game_slug, agent_b_spec, config, player=player_ids[1])
    except ValueError as e:
        print(f"  [skip] {e}", file=sys.stderr)
        return None

    state = game.initial_state()

    # Map player ids to agents
    agents = {player_ids[0]: agent_a, player_ids[1]: agent_b}

    max_steps = 10_000  # safety limit
    steps = 0
    while not game.is_terminal(state) and steps < max_steps:
        state_dict = _serialize(state)
        awaiting = state_dict.get("awaiting", [])
        # Fallback for games that use current_player/phase instead of awaiting
        if not awaiting:
            current_player = state_dict.get("current_player")
            phase = state_dict.get("phase", "")
            if current_player and phase != "complete":
                awaiting = [current_player]
        if not awaiting:
            break

        for player in list(awaiting):
            agent = agents.get(player)
            if agent is None:
                break
            history = state_dict.get("history", [])
            action = agent.act(history)
            try:
                state = game.apply_action(state, player, action)
                state_dict = _serialize(state)
            except Exception as e:
                print(f"  [warn] {player} action error: {e}", file=sys.stderr)
                break
        steps += 1

    if not game.is_terminal(state):
        return None

    results = game.compute_results(state)
    return results


def run_tournament(
    game_slugs: list[str],
    agent_specs: list[str],
    n_games: int,
    default_config: dict | None = None,
    seed: int | None = None,
) -> dict:
    """
    Run a round-robin tournament across games and agents.
    Returns a dict with per-game stats and overall leaderboard.
    """
    registry = AgentRegistry()
    evaluator = MatchEvaluator(registry)
    benchmark = BenchmarkReport()

    game_results: dict[str, dict] = {}  # game_slug -> {matchup_key -> [results]}
    per_agent_payoffs: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for game_slug in game_slugs:
        print(f"\n{'='*60}")
        print(f"  Game: {game_slug}")
        print(f"{'='*60}")

        # Build config
        base_cfg: dict = {"game": game_slug}
        if default_config:
            base_cfg.update(default_config.get(game_slug, {}))

        # Add required n-player count if needed (public goods needs >=3)
        try:
            game_meta = REGISTRY.get_game(game_slug)
            min_players = game_meta.get("players", {}).get("min", 2)
            if min_players > 2 and "players" not in base_cfg:
                base_cfg["players"] = min(min_players, len(agent_specs))
        except GameRegistryError:
            pass

        try:
            config = REGISTRY.config_from_request(base_cfg)
        except Exception as e:
            print(f"  [skip] Could not build config: {e}", file=sys.stderr)
            continue

        player_ids = list(config.player_ids())
        n_players = len(player_ids)

        # Resolve agent specs
        available_classes = _get_agent_classes(game_slug)
        if "all" in agent_specs:
            resolved = list(available_classes.keys())
        else:
            resolved = agent_specs

        if len(resolved) < 2:
            print(f"  [skip] Need at least 2 agents, got: {resolved}", file=sys.stderr)
            continue

        matchup_stats: dict[str, list[float]] = defaultdict(list)
        extension = REGISTRY.metrics_extension(game_slug)
        declared = REGISTRY.get_metric_names(game_slug)

        if n_players == 2:
            pairs = list(itertools.combinations(resolved, 2))
        else:
            # N-player: use groups of n_players
            pairs = list(itertools.combinations(resolved, n_players))

        for combo in pairs:
            a_spec = combo[0]
            b_spec = combo[1] if len(combo) > 1 else combo[0]
            matchup_key = " vs ".join(combo)
            print(f"  Matchup: {matchup_key} ({n_games} games)")

            for i in range(n_games):
                seed_val = (seed or 0) * 10000 + i
                result = play_match(game_slug, a_spec, b_spec, config, seed_offset=seed_val)
                if result is None:
                    continue

                # Build a Match object for the evaluator
                history = result.get("history", [])
                config_dict = config.to_dict() if hasattr(config, "to_dict") else {}

                moves: list[Move] = []
                for entry in history:
                    round_num = entry.get("round", entry.get("step", 0))
                    actions = entry.get("actions") or entry.get("quantities") or \
                              entry.get("contributions") or {}
                    if isinstance(actions, dict) and actions:
                        payoffs = entry.get("payoffs") or entry.get("scores", {})
                        for pid, act in actions.items():
                            if act is not None:
                                moves.append(Move(
                                    agent_id=f"{combo[0] if pid == player_ids[0] else combo[1]}",
                                    round_number=round_num,
                                    action=act,
                                    payoff=float(payoffs.get(pid, 0.0)),
                                ))
                    elif entry.get("action"):
                        # Sequential game (centipede)
                        pid = entry.get("player", "A")
                        idx = player_ids.index(pid) if pid in player_ids else 0
                        agent_name = combo[idx] if idx < len(combo) else combo[0]
                        payoffs = entry.get("payoffs") or entry.get("scores", {})
                        moves.append(Move(
                            agent_id=agent_name,
                            round_number=round_num,
                            action=entry["action"],
                            payoff=float(payoffs.get(pid, 0.0)),
                        ))
                        # For terminal entries with payoffs, also record the other player's outcome
                        if payoffs:
                            for other_pid, other_payoff in payoffs.items():
                                if other_pid != pid:
                                    other_idx = player_ids.index(other_pid) if other_pid in player_ids else 1
                                    other_agent = combo[other_idx] if other_idx < len(combo) else combo[1]
                                    moves.append(Move(
                                        agent_id=other_agent,
                                        round_number=round_num,
                                        action="outcome",
                                        payoff=float(other_payoff),
                                    ))

                import uuid as _uuid
                match = Match(
                    match_id=str(_uuid.uuid4()),
                    game_type=game_slug,
                    agent_ids=list(combo),
                    moves=moves,
                    config=config_dict,
                )

                try:
                    rich = evaluator.evaluate(
                        match, extension=extension,
                        game_config=config_dict, declared_metrics=declared
                    )
                    benchmark.record_match(game_slug, rich)

                    for spec_i, pid in zip(combo, player_ids):
                        payoff = result.get("total_scores", {}).get(pid, 0.0)
                        per_agent_payoffs[spec_i][game_slug].append(float(payoff))
                        matchup_stats[f"{matchup_key}_{spec_i}"].append(float(payoff))
                except Exception as e:
                    print(f"    [warn] Evaluation error: {e}", file=sys.stderr)

        # Print game summary
        for spec in resolved:
            game_payoffs = per_agent_payoffs[spec].get(game_slug, [])
            if game_payoffs:
                print(f"    {spec:30s}  avg_payoff={np.mean(game_payoffs):.2f}  "
                      f"n={len(game_payoffs)}")

        game_results[game_slug] = {"matchup_stats": dict(matchup_stats)}

    # ── Leaderboard ────────────────────────────────────────────────────────
    all_agents = list(set(
        a for payoffs in per_agent_payoffs.values() for a in per_agent_payoffs
    ))
    if len(all_agents) < 2:
        all_agents = list(per_agent_payoffs.keys())

    report = benchmark.generate(registry, sorted(set(all_agents))) if len(all_agents) >= 2 else {}

    return {
        "game_results": game_results,
        "per_agent_payoffs": {
            agent: {game: float(np.mean(vals)) for game, vals in games.items()}
            for agent, games in per_agent_payoffs.items()
        },
        "leaderboard": report,
    }


def _print_report(result: dict) -> None:
    print("\n" + "="*70)
    print("  BENCHMARK LEADERBOARD")
    print("="*70)

    leaderboard = result.get("leaderboard", {})
    agents = leaderboard.get("agents", {})
    ranking = leaderboard.get("ranking", [])

    if not ranking:
        print("  (not enough data for leaderboard)")
        return

    print(f"\n  {'Agent':<30} {'Elo':>7}  {'α-Rank':>8}  {'Competitive':>12}  "
          f"{'Cooperative':>12}  {'Cognitive':>10}")
    print(f"  {'-'*30}  {'-'*7}  {'-'*8}  {'-'*12}  {'-'*12}  {'-'*10}")

    for agent_id in ranking:
        ad = agents.get(agent_id, {})
        elo = ad.get("elo")
        alpha = ad.get("alpha_rank")
        comp = ad.get("competitive_rationality")
        coop = ad.get("cooperative_reasoning")
        cog = ad.get("cognitive_depth")
        print(
            f"  {agent_id:<30}  "
            f"{elo:>7.1f}  " if elo else f"  {'N/A':>7}  ",
            end=""
        )
        print(
            f"{alpha:>8.4f}  " if alpha is not None else f"{'N/A':>8}  ",
            end=""
        )
        print(
            f"{comp:>12.3f}  " if comp is not None else f"{'N/A':>12}  ",
            end=""
        )
        print(
            f"{coop:>12.3f}  " if coop is not None else f"{'N/A':>12}  ",
            end=""
        )
        print(f"{cog:>10.3f}" if cog is not None else f"{'N/A':>10}")

    print(f"\n  Total matches: {leaderboard.get('total_matches', 0)}")


def main():
    parser = argparse.ArgumentParser(
        description="NashArena benchmark tournament runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--games", nargs="+", required=True,
        metavar="GAME",
        help="Game slugs to include (e.g. prisonersdilemma stag_hunt centipede)",
    )
    parser.add_argument(
        "--agents", nargs="+", default=["all"],
        metavar="AGENT",
        help="Agent class names (or 'all' for all built-in agents for each game)",
    )
    parser.add_argument(
        "--n-games", type=int, default=20,
        help="Number of games per matchup (default: 20)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--output-json", type=str, default=None,
        metavar="FILE",
        help="Write full results to a JSON file",
    )
    parser.add_argument(
        "--config", type=str, default=None,
        metavar="FILE",
        help="JSON file with per-game config overrides (e.g. {\"prisonersdilemma\": {\"rounds\": 20}})",
    )
    args = parser.parse_args()

    default_config: dict | None = None
    if args.config:
        with open(args.config) as f:
            default_config = json.load(f)

    results = run_tournament(
        game_slugs=args.games,
        agent_specs=args.agents,
        n_games=args.n_games,
        default_config=default_config,
        seed=args.seed,
    )
    _print_report(results)

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n  Results written to {args.output_json}")


if __name__ == "__main__":
    main()
