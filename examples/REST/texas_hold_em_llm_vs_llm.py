import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from datetime import datetime, timezone

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from openai import OpenAI

from nash_arena_sdk import ArenaClient
from games.core.texas_hold_em.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

PLAYER_A_MODEL = "deepseek-v4-pro"
PLAYER_B_MODEL = "glm-5.1"
NUM_HANDS = 3
VARIANT = "classic"

VALID_ACTIONS = ("fold", "check", "call", "raise")

HAND_RANKINGS = (
    "Hand rankings (high to low):\n"
    "  royal flush > straight flush > four of a kind > full house > flush\n"
    "  > straight > three of a kind > two pair > one pair > high card\n"
    "Card notation: rank+suit. Ranks: 2-9,T,J,Q,K,A. Suits: h(hearts),d(diamonds),c(clubs),s(spades).\n"
    "Example: Ah = Ace of hearts, Td = Ten of diamonds."
)


def parse_action(text):
    if not text:
        return "check"
    text_lower = text.strip().lower()
    for action in VALID_ACTIONS:
        if action in text_lower:
            return action
    return "check"


def build_prompt(state, player_label, is_face_up):
    hand_number = state.get("hand_number", 1)
    street = state.get("street", "preflop")
    hole_cards = state.get("hole_cards", {})
    community_cards = state.get("community_cards", [])
    chips = state.get("chips", {})
    pot = state.get("pot", 0.0)
    street_actions = state.get("street_actions", [])
    history = state.get("history", [])
    total_scores = state.get("total_scores", {})

    opponent = "B" if player_label == "A" else "A"

    my_cards = hole_cards.get(player_label, [])
    if is_face_up:
        opp_cards = hole_cards.get(opponent, [])
        opp_cards_str = ", ".join(opp_cards) if opp_cards else "none"
    else:
        opp_cards_str = "??, ??"

    community_str = ", ".join(community_cards) if community_cards else "none"
    my_chips = chips.get(player_label, 0)
    opp_chips = chips.get(opponent, 0)
    my_score = total_scores.get(player_label, 0)

    lines = [
        f"You are playing Texas Hold'em as player {player_label}.",
        f"Hand {hand_number}, street: {street}.",
        f"Your hole cards: {', '.join(my_cards) if my_cards else 'none'}",
        f"Opponent hole cards: {opp_cards_str}",
        f"Community cards: {community_str}",
        f"Your chips: {my_chips:.0f}  Opponent chips: {opp_chips:.0f}  Pot: {pot:.0f}",
        f"Your cumulative profit: {my_score:+.1f}",
    ]

    if street_actions:
        lines.append("Actions this street:")
        for sa in street_actions:
            p = sa.get("player", "?")
            a = sa.get("action", "?")
            b = sa.get("bet", None)
            if b is not None:
                lines.append(f"  {p} {a}s {b:.0f}")
            else:
                lines.append(f"  {p} {a}s")

    if history:
        lines.append("Previous hands:")
        for h in history[-3:]:
            r = h.get("result", {})
            outcome = r.get("outcome", "?")
            winner = r.get("winner", "?")
            lines.append(f"  Hand {h.get('hand', '?')}: {outcome}, winner={winner}")

    lines.append("")
    lines.append(HAND_RANKINGS)
    lines.append("")
    lines.append("Respond with exactly one word: fold, check, call, or raise. Do not explain.")
    return "\n".join(lines)


def make_system_msg(is_face_up):
    visibility = "You can see both players' hole cards." if is_face_up else "You can only see your own hole cards."
    return (
        f"You are an aggressive Texas Hold'em poker player. {visibility} "
        "Each hand you and your opponent take turns betting over 4 streets "
        "(preflop, flop, turn, river). "
        "Actions: fold (give up), check (pass if no bet), call (match bet), raise (increase bet by 2). "
        "Each player starts with 100 chips, ante is 1 per hand, bet size is 2. "
        "At showdown the best five-card poker hand wins the pot. "
        "IMPORTANT: Only fold when your hand is really bad. Prefer calling or raising. "
        "Do not fold preflop unless your cards are terrible (like 2-7 offsuit). "
        "Output ONLY one word. No other text."
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
            reasoning = getattr(completion.choices[0].message, "reasoning_content", "") or ""
            dt = time.time() - t0
            action = parse_action(content or reasoning)
            print(f"  [{model}] {dt:.1f}s -> {action}")
            return action, None
        except Exception as e:
            msg = str(e)[:80]
            print(f"  [{model}] attempt {attempt+1}/2: {msg}")
            time.sleep(5)
    print(f"  [{model}] FAILED - forfeiting hand")
    return None, "LLM call failed"


async def llm_move(model, system_msg, prompt, extra_body=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sync_llm_call, model, system_msg, prompt, extra_body)


def extract_tool_text(result):
    for item in result.content:
        if isinstance(item, types.TextContent):
            try:
                return json.loads(item.text)
            except json.JSONDecodeError:
                return {"raw": item.text}
    return {}


async def run_match(variant="classic", num_hands=3):
    is_face_up = variant == "classic"
    nash_api_key = os.environ["NASH_ARENA_API_KEY"]
    opencode_api_key = os.environ["OPENCODE_GO_API_KEY"]
    _client.api_key = opencode_api_key.strip()

    print(f"=== Texas Hold'em: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Variant: {variant} ({'face-up' if is_face_up else 'face-down'})")
    print(f"Hands: {num_hands}")
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

    arena = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "texas_hold_em",
        "variant": variant,
        "players": 2,
        "rounds": num_hands,
        "seed": 42,
    })
    created = arena.create_experiment(
        config,
        agents={"A": "remote", "B": "remote"},
        api_key=nash_api_key,
    )
    session_id = created["session_id"]
    key_a = created["player_tokens"]["A"]
    key_b = created["player_tokens"]["B"]
    print(f"Session: {session_id}")
    print()

    async with AsyncExitStack() as exit_stack:
        print(f"Starting MCP server for {PLAYER_A_MODEL} (Player A)...")
        mcp_a = await exit_stack.enter_async_context(
            ClientSession(*await exit_stack.enter_async_context(stdio_client(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "nash_arena.mcp_server"],
                    env={"NASH_ARENA_BASE_URL": NASH_ARENA_BASE_URL, "NASH_ARENA_KEY": key_a},
                )
            )))
        )
        await mcp_a.initialize()

        print(f"Starting MCP server for {PLAYER_B_MODEL} (Player B)...")
        mcp_b = await exit_stack.enter_async_context(
            ClientSession(*await exit_stack.enter_async_context(stdio_client(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "nash_arena.mcp_server"],
                    env={"NASH_ARENA_BASE_URL": NASH_ARENA_BASE_URL, "NASH_ARENA_KEY": key_b},
                )
            )))
        )
        await mcp_b.initialize()
        print("Both MCP servers ready.\n")

        system_msg = make_system_msg(is_face_up)
        no_thinking = {"thinking": {"type": "disabled"}}
        action_count = 0
        prev_history_len = 0
        mcp_by_player = {"A": (mcp_a, PLAYER_A_MODEL), "B": (mcp_b, PLAYER_B_MODEL)}

        while True:
            state_result = await mcp_a.call_tool("get_game_state")
            state = extract_tool_text(state_result)

            phase = state.get("phase", "")
            if phase == "complete":
                break

            awaiting = state.get("awaiting", [])
            if not awaiting:
                break

            current_player = awaiting[0]
            action_count += 1

            mcp, model_name = mcp_by_player[current_player]
            prompt = build_prompt(state, current_player, is_face_up)
            action, error = await llm_move(model_name, system_msg, prompt, extra_body=no_thinking)

            if error:
                print(f"  {model_name} forfeit - using fallback: check")
                await mcp.call_tool("submit_action", {"allocation": "check"})
            else:
                await mcp.call_tool("submit_action", {"allocation": action})

            state_after = extract_tool_text(await mcp_a.call_tool("get_game_state"))
            history = state_after.get("history", [])
            if len(history) > prev_history_len:
                last = history[-1]
                result = last.get("result", {})
                outcome = result.get("outcome", "")
                winner = result.get("winner", "")
                if outcome:
                    winner_label = (
                        PLAYER_A_MODEL if winner == "A"
                        else PLAYER_B_MODEL if winner == "B"
                        else "Tie"
                    )
                    print(f"  Hand {last.get('hand', '?')} done: {outcome}, winner={winner_label}")
                    print()
                prev_history_len = len(history)

        results = extract_tool_text(await mcp_a.call_tool("get_results"))

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
    print(f"Final: A({PLAYER_A_MODEL})={total_a:+.1f}  B({PLAYER_B_MODEL})={total_b:+.1f}")
    print()

    print("--- Metrics ---")
    hand_wins = metrics.get("hand_win_counts", {})
    win_rate = metrics.get("hand_win_rate", {})
    print(f"  Hand wins: {PLAYER_A_MODEL}={hand_wins.get('A', 0)} {PLAYER_B_MODEL}={hand_wins.get('B', 0)} Ties={hand_wins.get('Tie', 0)}")
    print(f"  Win rate: {PLAYER_A_MODEL}={win_rate.get('A', 0):.2f} {PLAYER_B_MODEL}={win_rate.get('B', 0):.2f}")
    print(f"  Showdowns: {metrics.get('showdown_count', 0)}")
    print(f"  Fold rate: {PLAYER_A_MODEL}={metrics.get('fold_rate', {}).get('A', 0):.2f} {PLAYER_B_MODEL}={metrics.get('fold_rate', {}).get('B', 0):.2f}")
    print(f"  Raise rate: {PLAYER_A_MODEL}={metrics.get('raise_rate', {}).get('A', 0):.2f} {PLAYER_B_MODEL}={metrics.get('raise_rate', {}).get('B', 0):.2f}")
    print(f"  Total actions: {action_count}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"texas_hold_em_{PLAYER_A_MODEL}_vs_{PLAYER_B_MODEL}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "texas_hold_em",
            "variant": variant,
            "player_a": PLAYER_A_MODEL,
            "player_b": PLAYER_B_MODEL,
            "hands": num_hands,
            "thinking": "disabled",
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


def main():
    parser = argparse.ArgumentParser(description="Run Texas Hold'em LLM match via remote agents")
    parser.add_argument(
        "--variant", "-v",
        choices=["classic", "face_down"],
        default=VARIANT,
        help="Game variant: classic (face-up) or face_down",
    )
    parser.add_argument(
        "--hands", "-n",
        type=int,
        default=NUM_HANDS,
        help="Number of hands to play (default: 3)",
    )
    args = parser.parse_args()
    asyncio.run(run_match(args.variant, args.hands))


if __name__ == "__main__":
    main()
