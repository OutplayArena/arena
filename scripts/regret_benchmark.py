"""Run auditable, repeated regret comparisons without requiring an Arena server."""

import argparse
import json
from pathlib import Path

import yaml
from arena.benchmarks.regret import BenchmarkConfig, benchmark_plan, run_benchmark
from arena.benchmarks.report import write_plots, write_report


def main() -> None:
    """Load a YAML experiment, stream trial checkpoints, and export comparisons."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, help="YAML configuration; defaults to a free mock study"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/regret-benchmark")
    )
    parser.add_argument(
        "--allow-model-calls",
        action="store_true",
        help="Explicitly permit configured model requests",
    )
    parser.add_argument(
        "--max-model-calls",
        type=int,
        default=0,
        help="Hard cap on completion attempts, including retries",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show the planned workload without model access",
    )
    args = parser.parse_args()
    try:
        data = yaml.safe_load(args.config.read_text()) if args.config else {}
        if not isinstance(data, dict):
            raise TypeError("benchmark configuration must be a mapping")
        config = BenchmarkConfig.from_dict(data)
        if args.dry_run:
            plan = benchmark_plan(config)
            print(
                json.dumps(
                    {k: v for k, v in plan.items() if k != "traces_by_seed"}, indent=2
                )
            )
            return
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with (args.output_dir / "trials.jsonl").open("x") as stream:

            def checkpoint(trial: dict) -> None:
                stream.write(json.dumps(trial, allow_nan=False) + "\n")
                stream.flush()

            report = run_benchmark(
                config,
                allow_model_calls=args.allow_model_calls,
                max_model_calls=args.max_model_calls,
                on_trial=checkpoint,
            )
        write_report(report, args.output_dir, write_trials=False)
        plotted = write_plots(report, args.output_dir)
    except (ValueError, TypeError, OSError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    failed = sum(t["status"] == "failed" for t in report["trials"])
    print(
        f"Saved {len(report['trials'])} trials ({failed} failed), {report['model_calls_used']} model attempts to {args.output_dir}"
    )
    if not plotted:
        print(
            "Optional curves: rerun in a new directory with uv run --with matplotlib python scripts/regret_benchmark.py"
        )
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
