import asyncio
import os
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

from outplayarena_sdk import ArenaClient
from games.core.rock_paper_scissors.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYARENA_BASE_URL = os.environ.get("OUTPLAYARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
NUM_ROUNDS = 10

VALID_MOVES = ("rock", "paper", "scissors")
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


def parse_move(text):
    text_lower = text.strip().lower()
    for move in VALID_MOVES:
        if move in text_lower:
            return move
    return "rock"


def build_prompt(state, player_label):
    history = state.get("history", [])
    round_num = state.get("round", 1)
    round_total = state.get("round_total", NUM_ROUNDS)
    total_scores = state.get("total_scores", {})

    lines = [
        f"You are playing Rock-Paper-Scissors as player {player_label}.",
        "Rock beats scissors, scissors beats paper, paper beats rock.",
        "Win = +1, tie = 0, loss = -1.",
        f"Round {round_num} of {round_total}.",
        f"Your score: {total_scores.get(player_label, 0)}.",
    ]
    if history:
        lines.append("Previous rounds:")
        for h in history[-3:]:
            actions = h.get("actions", {})
            scores = h.get("scores", {})
            winner = h.get("winner", "Tie")
            lines.append(
                f"  Round {h.get('round', '?')}: {player_label} chose {actions.get(player_label, '?')}, "
                f"opponent chose {actions.get('B' if player_label == 'A' else 'A', '?')}. "
                f"Result: {scores.get(player_label, 0)} points. Winner: {winner}"
            )
    lines.append("Respond with exactly one word: rock, paper, or scissors.")
    return "\n".join(lines)


def make_system_msg():
    return (
        "You are playing Rock-Paper-Scissors. "
        "Choose rock, paper, or scissors to maximize your cumulative score. "
        "Output ONLY one word (rock, paper, or scissors). No other text."
    )


def sync_llm_call(model, system_msg, prompt, extra_body=None):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        max_tokens=256,
        temperature=0.7,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body

    for attempt in range(2):
        try:
            t0 = time.time()
            completion = _client.chat.completions.create(**kwargs)
            content = completion.choices[0].message.content or ""
            dt = time.time() - t0
            move = parse_move(content)
            print(f"  [{model}] {dt:.1f}s -> {move}")
            return move, None
        except Exception as e:
            msg = str(e)[:80]
            print(f"  [{model}] attempt {attempt+1}/2: {msg}")
            time.sleep(5)
    print(f"  [{model}] FAILED - forfeiting round")
    return None, "LLM call failed"


async def llm_move(model, prompt, extra_body=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sync_llm_call, model, make_system_msg(), prompt, extra_body)


async def run_match():
    nash_api_key = os.environ["OUTPLAYARENA_API_KEY"]
    opencode_api_key = os.environ["OPENCODE_GO_API_KEY"]
    _client.api_key = opencode_api_key.strip()

    print(f"=== Rock-Paper-Scissors: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Rounds: {NUM_ROUNDS}")
    print("Both models: thinking disabled")
    print()

    print("Warming up LLM APIs...")
    for model in [PLAYER_A_MODEL, PLAYER_B_MODEL]:
        try:
            t0 = time.time()
            completion = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Say 'ready'"},
                ],
                max_tokens=256,
                temperature=0,
            )
            content = completion.choices[0].message.content or ""
            print(f"  [{model}] warmup OK ({len(content)} chars, {time.time() - t0:.1f}s)")
        except Exception as e:
            print(f"  [{model}] warmup failed ({e}), continuing anyway")
    print()

    arena = ArenaClient(OUTPLAYARENA_BASE_URL)
    config = config_from_dict({
        "game": "rock_paper_scissors",
        "variant": "classic",
        "players": 2,
        "rounds": NUM_ROUNDS,
        "seed": 42,
    })
    created = arena.create_experiment(
        config,
        agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL},
        api_key=nash_api_key,
    )
    session_id = created["session_id"]
    created["player_tokens"]["A"]
    created["player_tokens"]["B"]
    print(f"Session: {session_id}")
    print()

    player_a = ArenaClient.for_player(OUTPLAYARENA_BASE_URL, created, "A")
    player_b = ArenaClient.for_player(OUTPLAYARENA_BASE_URL, created, "B")

    no_thinking = {"thinking": {"type": "disabled"}}

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        state = player_a.get_state()
        if state.get("phase") == "complete":
            break

        prompt_a = build_prompt(state, "A")
        prompt_b = build_prompt(state, "B")

        (move_a, error_a), (move_b, error_b) = await asyncio.gather(
            llm_move(PLAYER_A_MODEL, prompt_a, extra_body=no_thinking),
            llm_move(PLAYER_B_MODEL, prompt_b, extra_body=no_thinking),
        )

        if error_a:
            move_a = "rock"
            print(f"  {PLAYER_A_MODEL} forfeit - using fallback: {move_a}")
        if error_b:
            move_b = "rock"
            print(f"  {PLAYER_B_MODEL} forfeit - using fallback: {move_b}")

        player_a.submit_action(move_a)
        player_b.submit_action(move_b)

        state_after = player_a.get_state()
        if state_after.get("history"):
            last = state_after["history"][-1]
            actions = last.get("actions", {})
            scores = last.get("scores", {})
            print(f"  {PLAYER_A_MODEL}={actions.get('A', '?')}  {PLAYER_B_MODEL}={actions.get('B', '?')}")
            print(f"  Scores: A={scores.get('A', 0):.1f} B={scores.get('B', 0):.1f} -> {last.get('winner', '?')}")
        print()

    results = player_a.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    winner_label = (
        f"{PLAYER_A_MODEL} (A)" if winner == "A"
        else f"{PLAYER_B_MODEL} (B)" if winner == "B"
        else "Tie"
    )
    print(f"Winner: {winner_label}")
    print(f"Final: A({PLAYER_A_MODEL})={total_a:.1f}  B({PLAYER_B_MODEL})={total_b:.1f}")
    print()

    print("─ Metrics ─")
    move_freqs = metrics.get("move_frequencies", {})
    for player, label in [("A", PLAYER_A_MODEL), ("B", PLAYER_B_MODEL)]:
        freqs = move_freqs.get(player, {})
        print(f"  {label}: rock={freqs.get('rock', 0):.2f} paper={freqs.get('paper', 0):.2f} scissors={freqs.get('scissors', 0):.2f}")

    win_counts = metrics.get("round_win_counts", {})
    print(f"  Win counts: {PLAYER_A_MODEL}={win_counts.get('A', 0)}, {PLAYER_B_MODEL}={win_counts.get('B', 0)}, Ties={win_counts.get('Tie', 0)}")
    print(f"  Round win rate: A={metrics.get('round_win_rate', {}).get('A', 0):.2f} B={metrics.get('round_win_rate', {}).get('B', 0):.2f}")
    print(f"  Average payoff: A={metrics.get('average_payoff', {}).get('A', 0):.2f} B={metrics.get('average_payoff', {}).get('B', 0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"rps_{PLAYER_A_MODEL}_vs_{PLAYER_B_MODEL}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "rock_paper_scissors",
            "player_a": PLAYER_A_MODEL,
            "player_b": PLAYER_B_MODEL,
            "rounds": NUM_ROUNDS,
            "thinking": "disabled",
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(run_match())
