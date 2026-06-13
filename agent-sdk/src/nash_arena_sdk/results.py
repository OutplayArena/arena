from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def format_results(results: dict, game: str | None = None) -> str:
    """Format game results as a human-readable string."""
    lines = []
    lines.append("=" * 56)

    winner = results.get("winner", "Unknown")
    if winner != "Tie" and winner != "Unknown":
        lines.append(f"Winner: {winner}")
    else:
        lines.append("Result: Tie")

    total_scores = results.get("total_scores", {})
    if total_scores:
        scores_str = "  ".join(f"{p}={s:.1f}" for p, s in sorted(total_scores.items()))
        lines.append(f"Final scores: {scores_str}")

    metrics = results.get("metrics", {})
    if metrics:
        lines.append("")
        lines.append("Metrics:")
        for key, value in sorted(metrics.items()):
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            elif isinstance(value, dict):
                lines.append(f"  {key}:")
                for k, v in sorted(value.items()):
                    if isinstance(v, float):
                        lines.append(f"    {k}: {v:.4f}")
                    else:
                        lines.append(f"    {k}: {v}")
            else:
                lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def save_results(
    results: dict,
    output_dir: str | Path = "results",
    game: str | None = None,
    session_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Save game results to a JSON file.

    Returns the path to the saved file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    game_name = game or results.get("game", "game")
    filename = f"{game_name}_{timestamp}.json"
    if session_id:
        filename = f"{game_name}_{session_id[:8]}_{timestamp}.json"

    path = output_dir / filename

    payload = {
        "game": game_name,
        "session_id": session_id or results.get("session_id"),
        "timestamp": timestamp,
        "results": results,
    }
    if extra:
        payload.update(extra)

    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    return path
