"""Reproducible offline RPS comparisons; no server, credentials, or LLM calls."""

import argparse
import csv
import json
import random
from pathlib import Path

from arena.metrics.regret_baselines import replay_baseline
from games.core.rock_paper_scissors.agent import CounterAgent
from games.core.rock_paper_scissors.config import VALID_MOVES
from games.core.rock_paper_scissors.engine import RPSGame


def experiment(rounds: int = 100, seed: int = 7) -> dict:
    """Replay the existing CounterAgent and two learners against four traces."""
    if rounds < 1:
        raise ValueError("rounds must be positive")
    rng = random.Random(seed)
    traces = {
        "constant": ["rock"] * rounds,
        "cyclic": [VALID_MOVES[t % 3] for t in range(rounds)],
        "switching": ["rock" if t < rounds // 2 else "scissors" for t in range(rounds)],
        "uniform": [rng.choice(VALID_MOVES) for _ in range(rounds)],
    }
    output = {
        "seed": seed,
        "rounds": rounds,
        "mode": "offline_fixed_trace",
        "traces": {},
    }
    prior_rng = random.getstate()
    try:
        for name, opponents in traces.items():
            random.seed(seed)
            engine = RPSGame(num_rounds=rounds)
            state = engine.initial_state()
            agent = CounterAgent(player="A")
            actions = []
            for opponent in opponents:
                action = agent.act(state.history)
                actions.append(action)
                state = engine.apply_action(state, "A", action)
                state = engine.apply_action(state, "B", opponent)
            results = engine.compute_results(state)
            adapter = engine.metrics_engine.regret_game({})
            output["traces"][name] = {
                "opponent_actions": opponents,
                "engine_results": results,
                "agents": {
                    "counter_agent": {
                        "actions": actions,
                        "external_regret": results["metrics"]["external_regret"]["A"],
                    },
                    **{
                        algo: replay_baseline(adapter, opponents, algo, seed=seed)
                        for algo in ("ftpl", "ftrl")
                    },
                },
            }
    finally:
        random.setstate(prior_rng)
    return output


def write_outputs(result: dict, output_dir: Path) -> None:
    """Write JSON and tidy prefix CSV, plus SVG curves when Matplotlib is installed."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    with (output_dir / "curves.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            ["trace", "agent", "round", "cumulative", "average", "normalized_average"]
        )
        for trace, data in result["traces"].items():
            for agent, run in data["agents"].items():
                for point in run["external_regret"]["series"]:
                    writer.writerow(
                        [
                            trace,
                            agent,
                            *(
                                point[k]
                                for k in (
                                    "round",
                                    "cumulative",
                                    "average",
                                    "normalized_average",
                                )
                            ),
                        ]
                    )
    write_plots(result, output_dir)


def write_plots(result: dict, output_dir: Path) -> bool:
    """Write reproducible standalone Matplotlib figures if the optional package exists."""
    try:
        import matplotlib
    except ImportError:
        print(
            "For SVG plots, run with: uv run --with matplotlib python scripts/external_regret_example.py"
        )
        return False
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    with plt.rc_context({"svg.fonttype": "none", "svg.hashsalt": "external_regret"}):
        for metric in ("cumulative", "average"):
            fig, axes = plt.subplots(
                len(result["traces"]), 1, figsize=(9, 11), layout="constrained"
            )
            for ax, (trace, data) in zip(axes, result["traces"].items()):
                for agent, run in data["agents"].items():
                    points = run["external_regret"]["series"]
                    ax.plot(
                        [p["round"] for p in points],
                        [p[metric] for p in points],
                        label=agent,
                    )
                ax.axhline(0, color="gray", linewidth=0.8)
                ax.set(
                    title=trace, xlabel="Round", ylabel=f"{metric.capitalize()} regret"
                )
                ax.legend(loc="best")
            fig.suptitle(f"RPS offline fixed-trace replay: seed {result['seed']}")
            svg_path = output_dir / f"{metric}.svg"
            fig.savefig(svg_path, metadata={"Date": None})
            svg_path.write_text(
                "\n".join(line.rstrip() for line in svg_path.read_text().splitlines())
                + "\n"
            )
            fig.savefig(output_dir / f"{metric}.png", dpi=150)
            plt.close(fig)
    return True


def main() -> None:
    """Run the example with a configurable horizon and seed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/external_regret")
    )
    args = parser.parse_args()
    result = experiment(args.rounds, args.seed)
    write_outputs(result, args.output_dir)
    print(f"Wrote offline comparison outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
