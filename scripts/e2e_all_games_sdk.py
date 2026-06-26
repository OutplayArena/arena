"""
End-to-end games test using the OutplayArena SDK.

Runs all 10 games with GLM-5.1 (Player A) vs DeepSeek V4 Pro (Player B/C)
via OpenCode Zen. 2 rounds per game, no thinking for either model.

Uses the SDK's per-game agents (quick_play) which handle action format
parsing correctly for every game, including texas_hold_em.

Environment:
    OUTPLAYARENA_BASE_URL  Backend REST API (default http://127.0.0.1:8000/api)
    OUTPLAYARENA_API_KEY   Bearer token (Arena account API key)
    OPENCODE_GO_API_KEY         OpenCode Zen API key
"""
import asyncio
import os
import sys
import time
from typing import Any

from outplayarena_sdk.quick_play import _quick_play_async

sys.stdout.reconfigure(line_buffering=True)

ARENA_URL = os.environ.get("OUTPLAYARENA_BASE_URL", "http://127.0.0.1:8000/api")
ARENA_API_KEY = os.environ.get("OUTPLAYARENA_API_KEY", "")
OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"
OPENCODE_API_KEY = (
    os.environ.get("OPENCODE_GO_API_KEY")
    or os.environ.get("OPENCODE_API_KEY", "")
)
JWT_SECRET = os.environ.get("JWT_SECRET", "")

if not ARENA_API_KEY:
    sys.exit("ERROR: OUTPLAYARENA_API_KEY env var is required")
if not OPENCODE_API_KEY:
    sys.exit("ERROR: OPENCODE_GO_API_KEY (or OPENCODE_API_KEY) env var is required")
if not JWT_SECRET:
    sys.exit("ERROR: JWT_SECRET env var is required (must match backend's)")

GLM_MODEL = "glm-5.1"
DEEPSEEK_MODEL = "deepseek-v4-pro"
NUM_ROUNDS = 2

GAMES: list[tuple[str, int, dict[str, Any]]] = [
    ("stag_hunt",            2, {}),
    ("prisonersdilemma",     2, {}),
    ("ultimatum",            2, {}),
    ("colonelblotto",        2, {}),
    ("battle_of_the_sexes",  2, {}),
    ("cournot_duopoly",      2, {}),
    ("rock_paper_scissors",  2, {}),
    ("centipede",            2, {}),
    ("texas_hold_em",        2, {}),
    ("public_goods",         3, {"players": 3, "endowment": 10, "multiplier": 1.5}),
]


def spec_for(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "api_key": OPENCODE_API_KEY,
        "base_url": OPENCODE_BASE_URL,
        "reasoning_effort": "none",  # No thinking
    }


async def run_one(game: str, num_players: int, game_config: dict[str, Any]) -> dict[str, Any]:
    print(f"\n{'=' * 60}")
    print(f"GAME: {game}  ({num_players}P)")
    print(f"{'=' * 60}")

    agents: dict[str, dict[str, Any]] = {"A": spec_for(GLM_MODEL)}
    if num_players >= 2:
        agents["B"] = spec_for(DEEPSEEK_MODEL)
    if num_players >= 3:
        agents["C"] = spec_for(DEEPSEEK_MODEL)

    print(f"  Players: {', '.join(f'{p}={m['model']}' for p, m in agents.items())}")
    print(f"  Rounds: {NUM_ROUNDS}  Thinking: off")
    print()

    config = {"rounds": NUM_ROUNDS, **game_config}

    t0 = time.time()
    try:
        results = await _quick_play_async(
            game=game,
            agents=agents,
            arena_url=ARENA_URL,
            arena_api_key=ARENA_API_KEY,
            config=config,
            mcp_url="",  # Force REST (the SDK's MCP transport is flaky in this env)
            jwt_secret=JWT_SECRET,
            poll_interval=1.0,
            max_tools_per_turn=4,
            verbose=False,  # Set to True to see LLM tool-call traces
        )
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return {"game": game, "error": str(exc)}

    dt = time.time() - t0

    session_id = results.get("session_id", "?")
    total_scores = results.get("total_scores", {})
    winner = results.get("winner", "?")

    print(f"  Session: {session_id}  ({dt:.0f}s)")
    print(f"  Final:   {total_scores}")
    print(f"  Winner:  {winner}")
    print(f"  Replay:  http://localhost:5173/play/{game}/{session_id}")

    return {
        "game": game,
        "session_id": session_id,
        "duration_s": round(dt),
        "total_scores": total_scores,
        "winner": winner,
    }


async def main() -> None:
    print(f"ARENA: {ARENA_URL}")
    print(f"ZEN:   {OPENCODE_BASE_URL}")
    print(f"Games: {len(GAMES)}")
    print()

    summary: list[dict[str, Any]] = []
    for game, num_players, game_config in GAMES:
        result = await run_one(game, num_players, game_config)
        summary.append(result)
        await asyncio.sleep(2)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    glm_wins = 0
    deepseek_wins = 0
    ties = 0
    for r in summary:
        if "error" in r:
            print(f"  {r['game']:25s}  ERROR: {r['error'][:60]}")
            ties += 1
            continue
        scores = r.get("total_scores", {})
        a = scores.get("A", "?")
        b = scores.get("B", "?")
        c = scores.get("C", "-")
        winner = r.get("winner", "?")
        dur = r.get("duration_s", "?")
        print(f"  {r['game']:25s}  A={a:<6}  B={b:<6}  C={c:<6}  Winner: {winner:<6}  ({dur}s)")
        if winner == "A":
            glm_wins += 1
        elif winner in ("B", "C"):
            deepseek_wins += 1
        else:
            ties += 1
    print()
    print(f"GLM wins: {glm_wins}  DeepSeek wins: {deepseek_wins}  Ties/errors: {ties}")


if __name__ == "__main__":
    asyncio.run(main())
