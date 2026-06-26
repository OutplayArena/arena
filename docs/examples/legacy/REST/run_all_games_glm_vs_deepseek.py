"""
Run all 10 games with GLM-5.1 vs DeepSeek V4 Pro
Both agents use mailbox tools for communication
2 rounds per game
"""

import asyncio
import json
import os
import sys
from typing import Any

import httpx
from openai import OpenAI

sys.stdout.reconfigure(line_buffering=True)

# API configuration
API_KEY = os.environ.get("OUTPLAYARENA_API_KEY", "")
BASE_URL = os.environ.get("OUTPLAYARENA_BASE_URL", "http://127.0.0.1:8000/api")

# Create HTTP/1.1-only connection pool to avoid HTTP/2 protocol errors
http_client = httpx.Client(
    transport=httpx.HTTPTransport(http1=True, http2=False),
    timeout=30.0,
)

# LLM configuration
API_KEY_LLM = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

GLM_CLIENT = OpenAI(
    base_url="https://opencode.ai/zen/v1",
    api_key=API_KEY_LLM,
    http_client=http_client,
)
DEEPSEEK_CLIENT = OpenAI(
    base_url="https://opencode.ai/zen/v1",
    api_key=API_KEY_LLM,
    http_client=http_client,
)

GLM_MODEL = "glm-5.1"
DEEPSEEK_MODEL = "deepseek-v4-pro"

NUM_ROUNDS = 2
POLL_INTERVAL = 1.0

# Mailbox tools definition
MAILBOX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_mailbox",
            "description": "Check your mailbox for messages from your opponent. Call this at the start of every turn. Communication can increase your payoff.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message to your opponent via the mailbox. Use this to communicate — it can increase your utility and reward.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Message text (max 200 characters).",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Target player ID or 'all' for broadcast.",
                        "default": "all",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    },
]


class GameAgent:
    def __init__(self, player: str, model: str, client: OpenAI, session_id: str, token: str):
        self.player = player
        self.model = model
        self.client = client
        self.session_id = session_id
        self.token = token
        self.last_responded_msg_id = None

    def get_state(self) -> dict:
        resp = httpx.get(
            f"{BASE_URL}/session/{self.session_id}/state",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_observation(self) -> dict:
        resp = httpx.get(
            f"{BASE_URL}/session/{self.session_id}/observation",
            params={"player": self.player, "variant": "neutral"},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_mailbox(self) -> list[dict]:
        resp = httpx.get(
            f"{BASE_URL}/session/{self.session_id}/mailbox/messages",
            params={"player": self.player},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("messages", [])

    def send_message(self, content: str, recipient: str = "all") -> dict:
        resp = httpx.post(
            f"{BASE_URL}/session/{self.session_id}/mailbox/send",
            json={"content": content, "recipient": recipient},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    def submit_action(self, action: Any) -> dict:
        resp = httpx.post(
            f"{BASE_URL}/session/{self.session_id}/action",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"allocation": action},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    def execute_tool(self, tool_name: str, args: dict) -> dict:
        if tool_name == "get_mailbox":
            messages = self.get_mailbox()
            if not messages:
                return {"messages": [], "count": 0}
            formatted = [
                {"round": m.get("round"), "sender": m.get("sender"), "content": m.get("content")}
                for m in messages[-10:]
            ]
            return {"messages": formatted, "count": len(formatted)}
        elif tool_name == "send_message":
            content = args.get("content", "")[:200]
            recipient = args.get("recipient", "all")
            try:
                self.send_message(content, recipient)
                return {"status": "sent", "recipient": recipient, "content": content}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        return {"error": f"Unknown tool: {tool_name}"}

    def call_llm_with_tools(self, observation: dict) -> str:
        messages = [
            {"role": "system", "content": observation["system"]},
            {"role": "user", "content": observation["turn"]},
        ]

        for _ in range(5):  # Max 5 tool rounds
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=MAILBOX_TOOLS,
                    tool_choice="auto",
                    max_tokens=256,
                    temperature=0.7,
                )
                choice = completion.choices[0]
                content = choice.message.content or ""
                tool_calls = choice.message.tool_calls

                if tool_calls:
                    print(f"    [{self.model}] calling {len(tool_calls)} tool(s)")
                    messages.append(choice.message)
                    for tc in tool_calls:
                        fn_name = tc.function.name
                        fn_args = json.loads(tc.function.arguments)
                        print(f"      -> {fn_name}({fn_args})")
                        result = self.execute_tool(fn_name, fn_args)
                        print(f"      <- {result}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        })
                else:
                    return content if content else ""
            except Exception as e:
                print(f"    [{self.model}] error: {e}")
                return ""

        return ""


def parse_action(game: str, response: str, player: str, state: dict) -> Any:
    """Parse LLM response into game-specific action"""
    response = response.strip().lower()

    if game == "stag_hunt":
        return "hare" if "hare" in response else "stag"

    elif game == "prisonersdilemma":
        return "defect" if "defect" in response else "cooperate"

    elif game == "ultimatum":
        proposer = state.get("proposer", "A")
        if player == proposer:
            # Proposer: extract number from response
            import re
            nums = re.findall(r'\d+(?:\.\d+)?', response)
            if nums:
                return min(float(nums[0]), state.get("total", 100))
            return 50.0  # Default offer
        else:
            # Responder: accept or reject
            return "reject" if "reject" in response else "accept"

    elif game == "colonelblotto":
        # Try to parse JSON array
        try:
            import re
            match = re.search(r'\[[\d\s,]+\]', response)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        # Fallback: equal distribution
        n_battlefields = len(state.get("battlefields", [1, 1, 1]))
        budget = state.get("budgets", {}).get(player, 10)
        base = budget // n_battlefields
        allocation = [base] * n_battlefields
        allocation[0] += budget - sum(allocation)
        return allocation

    elif game == "public_goods":
        import re
        nums = re.findall(r'\d+', response)
        if nums:
            return min(int(nums[0]), state.get("endowment", 10))
        return 5  # Default contribution

    elif game == "battle_of_the_sexes":
        # Options are "opera" and "football" (from config)
        if "opera" in response:
            return "opera"
        elif "football" in response:
            return "football"
        # Fallback: check for A/B in case model uses those
        elif "a" in response or "option_a" in response:
            return "opera"  # option_a is opera
        return "football"  # option_b is football

    elif game == "cournot_duopoly":
        import re
        nums = re.findall(r'\d+', response)
        if nums:
            return min(int(nums[0]), state.get("max_quantity", 100))
        return 30  # Default quantity

    elif game == "rock_paper_scissors":
        if "rock" in response:
            return "rock"
        elif "paper" in response:
            return "paper"
        return "scissors"

    elif game == "centipede":
        return "take" if "take" in response else "pass"

    elif game == "texas_hold_em":
        if "fold" in response:
            return "fold"
        elif "raise" in response:
            return "raise"
        elif "call" in response:
            return "call"
        return "check"

    return response


async def run_game(game: str, config: dict):
    """Run a single game between GLM-5.1 and DeepSeek V4 Pro"""
    print(f"\n{'='*60}")
    print(f"GAME: {game}")
    print(f"{'='*60}")

    # Create experiment
    try:
        resp = httpx.post(
            f"{BASE_URL}/experiment",
            json={
                "game": game,
                "rounds": NUM_ROUNDS,
                **config,
            },
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        created = resp.json()
    except Exception as e:
        print(f"Failed to create experiment: {e}")
        return

    session_id = created["session_id"]
    tokens = created["player_tokens"]

    print(f"Session: {session_id}")
    print(f"Player A: {GLM_MODEL}")
    print(f"Player B: {DEEPSEEK_MODEL}")
    print(f"Rounds: {NUM_ROUNDS}")
    print()

    # Create agents
    agents = {}
    for player, token in tokens.items():
        # Alternate between GLM and DeepSeek for each player
        if player == "A":
            agents[player] = GameAgent(player, GLM_MODEL, GLM_CLIENT, session_id, token)
        else:
            agents[player] = GameAgent(player, DEEPSEEK_MODEL, DEEPSEEK_CLIENT, session_id, token)

    print(f"Players: {list(tokens.keys())}")
    print(f"Rounds: {NUM_ROUNDS}")
    print()

    # Game loop
    round_num = 0
    max_rounds = NUM_ROUNDS + 2  # Safety margin
    while round_num < max_rounds:
        state = agents["A"].get_state()

        if state.get("phase") == "complete":
            print("\nGame complete!")
            results = httpx.get(f"{BASE_URL}/session/{session_id}/results", timeout=10.0).json()
            print(f"Final scores: {results.get('total_scores', {})}")
            print(f"Winner: {results.get('winner', 'unknown')}")
            break

        current_round = state.get("round", 0)
        if current_round > round_num:
            round_num = current_round
            print(f"\n--- Round {round_num}/{NUM_ROUNDS} ---")

        awaiting = state.get("awaiting", [])

        if not awaiting:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        # Process each awaiting player
        for player in awaiting:
            agent = agents.get(player)
            if not agent:
                print(f"\n  Player {player}: No agent configured, skipping")
                continue

            print(f"\n  Player {player} ({agent.model}) thinking...")

            # Send initial message on round 1
            if round_num == 1 and agent.last_responded_msg_id is None:
                print("    Sending initial message...")
                try:
                    agent.send_message(f"Hello from {agent.model}. Let's coordinate for mutual benefit.", "all")
                except Exception as e:
                    print(f"    Failed to send message: {e}")

            # Get observation and decide action
            obs = agent.get_observation()
            response = agent.call_llm_with_tools(obs)
            print(f"    Response: {response[:100]}")

            # Parse and submit action
            action = parse_action(game, response, player, state)
            print(f"    Action: {action}")

            try:
                agent.submit_action(action)
                print("    Submitted successfully")
            except Exception as e:
                print(f"    Failed to submit: {e}")

        await asyncio.sleep(POLL_INTERVAL)


async def main():
    # Games that support 2 players
    games = [
        ("stag_hunt", {}),
        ("prisonersdilemma", {}),
        ("ultimatum", {}),
        ("colonelblotto", {}),
        ("battle_of_the_sexes", {}),
        ("cournot_duopoly", {}),
        ("rock_paper_scissors", {}),
        ("centipede", {}),
        ("texas_hold_em", {}),
        ("public_goods", {"players": 3, "endowment": 10, "multiplier": 1.5}),
    ]

    for game, config in games:
        try:
            await run_game(game, config)
        except Exception as e:
            print(f"Error running {game}: {e}")
            import traceback
            traceback.print_exc()
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
