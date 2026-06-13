from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def format_results(results: dict, game: str | None = None) -> str:
    """Format game results as a human-readable string.

    Produces a formatted multi-line string containing the winner, final
    scores for each player, and any available metrics. Designed for
    console output and logging.

    Args:
        results: A dictionary containing game results. Expected keys
            include ``"winner"`` (str), ``"total_scores"`` (dict mapping
            player names to float scores), and ``"metrics"`` (dict of
            metric names to values, which may be nested).
        game: Optional game name. Currently unused but reserved for
            future formatting variations.

    Returns:
        A formatted string with a separator line, the winner or tie
        result, final scores, and any metrics.

    Examples:
        >>> results = {
        ...     "winner": "Alice",
        ...     "total_scores": {"Alice": 3.0, "Bob": 1.0},
        ...     "metrics": {"nash_distance": 0.1234},
        ... }
        >>> print(format_results(results))
        ========================================================
        Winner: Alice
        Final scores: Alice=3.0  Bob=1.0

        Metrics:
          nash_distance: 0.1234
    """
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
    """Save game results to a timestamped JSON file.

    Creates the output directory if it does not exist. The filename is
    constructed from the game name, an optional session ID prefix, and
    a UTC timestamp. The JSON payload includes the game name, session
    ID, timestamp, the full results dict, and any extra fields.

    Args:
        results: A dictionary containing game results (winner, scores,
            metrics, etc.).
        output_dir: Directory where the JSON file will be written.
            Created if it does not exist. Defaults to ``"results"``.
        game: Game name used in the filename and payload. Falls back
            to ``results["game"]`` and then ``"game"`` if not provided.
        session_id: Optional session identifier. If provided, the first
            8 characters are included in the filename.
        extra: Optional dictionary of additional key-value pairs to
            merge into the top-level JSON payload.

    Returns:
        The path to the saved JSON file.

    Examples:
        >>> results = {"winner": "Alice", "total_scores": {"Alice": 3.0}}
        >>> path = save_results(results, output_dir="/tmp/results", game="blotto")
        >>> path.name.startswith("blotto_")
        True
        >>> path.suffix
        '.json'
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
