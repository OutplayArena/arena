"""Descriptive summaries and exportable comparisons for matched regret trials."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

METRICS = ("cumulative", "average", "normalized_average")


def _stats(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "n": len(values),
        "mean": mean(values),
        "stddev": stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def summarize(trials: list[dict]) -> dict:
    """Summarize complete runs and matched differences, retaining failure counts.

    The shaded range is the observed min/max across successful repetitions.
    Neither that range nor sample standard deviation is a confidence interval.
    Failed trajectories contribute no fabricated zero regret to numeric means.
    """
    groups = defaultdict(list)
    for trial in trials:
        groups[(trial["game"], trial["trace"], trial["candidate"])].append(trial)
    summaries = []
    for (game, trace, candidate), members in sorted(groups.items()):
        complete = [
            t
            for t in members
            if t["status"] == "completed"
            and t["external_regret"]["status"] == "available"
        ]
        lengths = {t["external_regret"]["num_rounds"] for t in complete}
        if len(lengths) > 1:
            raise ValueError("cannot aggregate unequal horizons")
        series = []
        for index in range(next(iter(lengths), 0)):
            point = {"round": index + 1}
            for metric in METRICS:
                values = [
                    t["external_regret"]["series"][index][metric] for t in complete
                ]
                point[metric] = _stats([v for v in values if v is not None])
            series.append(point)
        summaries.append(
            {
                "game": game,
                "trace": trace,
                "candidate": candidate,
                "candidate_kind": members[0]["candidate_kind"],
                "attempted_runs": len(members),
                "completed_runs": len(complete),
                "failed_runs": len(members) - len(complete),
                "actual_total_payoff": _stats(
                    [t["external_regret"]["actual_total_payoff"] for t in complete]
                ),
                "final": {m: series[-1][m] if series else None for m in METRICS},
                "series": series,
            }
        )
    pairs = []
    for group in summaries:
        if group["candidate_kind"] not in {"llm", "mock"}:
            continue
        for reference in ("ftpl", "ftrl"):
            own = groups[(group["game"], group["trace"], group["candidate"])]
            other = groups.get((group["game"], group["trace"], reference), [])
            if not other:
                continue
            baseline = {
                t["seed"]: t
                for t in other
                if t["status"] == "completed"
                and t["external_regret"]["status"] == "available"
            }
            differences = []
            for trial in own:
                comparator = baseline.get(trial["seed"])
                if (
                    trial["status"] != "completed"
                    or comparator is None
                    or trial["external_regret"]["status"] != "available"
                    or trial["external_regret"]["normalized_average"] is None
                    or comparator["external_regret"]["normalized_average"] is None
                ):
                    continue
                if trial["opponent_actions"] != comparator["opponent_actions"]:
                    raise ValueError(
                        "paired comparisons require identical opponent traces"
                    )
                differences.append(
                    trial["external_regret"]["normalized_average"]
                    - comparator["external_regret"]["normalized_average"]
                )
            pairs.append(
                {
                    "game": group["game"],
                    "trace": group["trace"],
                    "candidate": group["candidate"],
                    "reference": reference,
                    "paired_runs": len(differences),
                    "excluded_runs": len(own) - len(differences),
                    "normalized_average_difference": _stats(differences),
                    "interpretation": "candidate minus reference; negative favors candidate",
                }
            )
    return {
        "spread": "sample standard deviation and observed min/max; not confidence intervals",
        "groups": summaries,
        "paired_comparisons": pairs,
    }


def write_report(report: dict, output_dir: Path, *, write_trials: bool = True) -> None:
    """Export public configuration, raw trial audits, summary JSON, and tidy CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    public = {k: v for k, v in report.items() if k != "trials"}
    (output_dir / "report.json").write_text(
        json.dumps(public, indent=2, allow_nan=False) + "\n"
    )
    if write_trials:
        with (output_dir / "trials.jsonl").open("w") as stream:
            for trial in report["trials"]:
                stream.write(json.dumps(trial, allow_nan=False) + "\n")
    with (output_dir / "curves.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "game",
                "trace",
                "candidate",
                "completed_runs",
                "failed_runs",
                "round",
                "metric",
                "mean",
                "stddev",
                "min",
                "max",
            ]
        )
        for group in report["summary"]["groups"]:
            for point in group["series"]:
                for metric in METRICS:
                    stats = point[metric]
                    writer.writerow(
                        [
                            group["game"],
                            group["trace"],
                            group["candidate"],
                            group["completed_runs"],
                            group["failed_runs"],
                            point["round"],
                            metric,
                            *(
                                [stats[k] for k in ("mean", "stddev", "min", "max")]
                                if stats
                                else [None] * 4
                            ),
                        ]
                    )


def write_plots(report: dict, output_dir: Path) -> bool:
    """Plot means and observed repetition ranges with optional Matplotlib."""
    try:
        import matplotlib
    except ImportError:
        return False
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    groups = report["summary"]["groups"]
    traces = sorted({g["trace"] for g in groups})
    with plt.rc_context({"svg.fonttype": "none", "svg.hashsalt": "regret_benchmark"}):
        fig, axes = plt.subplots(
            len(traces),
            2,
            squeeze=False,
            figsize=(12, 3.2 * len(traces)),
            layout="constrained",
        )
        for row, trace in enumerate(traces):
            for col, metric in enumerate(("cumulative", "average")):
                ax = axes[row][col]
                for group in groups:
                    if group["trace"] != trace or not group["series"]:
                        continue
                    points = group["series"]
                    x = [p["round"] for p in points]
                    kind = " [scripted]" if group["candidate_kind"] == "mock" else ""
                    label = f"{group['candidate']}{kind} (n={group['completed_runs']}, failed={group['failed_runs']})"
                    (line,) = ax.plot(
                        x, [p[metric]["mean"] for p in points], label=label
                    )
                    ax.fill_between(
                        x,
                        [p[metric]["min"] for p in points],
                        [p[metric]["max"] for p in points],
                        color=line.get_color(),
                        alpha=0.15,
                    )
                empty = [
                    f"{g['candidate']}: 0/{g['attempted_runs']} complete"
                    for g in groups
                    if g["trace"] == trace and not g["series"]
                ]
                if empty:
                    ax.text(
                        0.01,
                        0.98,
                        "; ".join(empty),
                        transform=ax.transAxes,
                        va="top",
                        fontsize="small",
                    )
                ax.axhline(0, color="gray", linewidth=0.8)
                ax.set(
                    title=f"{trace}: {metric} regret", xlabel="Round", ylabel="Regret"
                )
                if ax.lines and ax.get_legend_handles_labels()[0]:
                    ax.legend(fontsize="small")
        mode = (
            "Offline fixed-trace replay"
            if any(g["candidate_kind"] == "llm" for g in groups)
            else "Offline fixed-trace replay (no model calls)"
        )
        fig.suptitle(mode + "; shading = observed min–max, not confidence intervals")
        svg = output_dir / "comparison.svg"
        fig.savefig(svg, metadata={"Date": None})
        svg.write_text(
            "\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n"
        )
        fig.savefig(output_dir / "comparison.png", dpi=140)
        plt.close(fig)
    return True
