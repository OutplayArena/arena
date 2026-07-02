"""Play Prisoner's Dilemma against a live LLM agent.

Configure a game in the OutplayArena UI with Player A = "Interactive (Human
Player)" and Player B = "Remote Agent (API)". After clicking Start, open the
"API Keys" panel on the Play tab and copy the session key it shows you.

Usage:
    export SESSION_KEY="nks_..."       # copied from the OutplayArena UI
    export OPENAI_API_KEY="sk-..."     # or swap LLMConfig below for another provider
    python play_vs_agent.py
"""

import base64
import os

from outplayarena_sdk import LLMConfig, PrisonersDilemmaAgent

ARENA_URL = os.environ.get("ARENA_URL", "https://arena.core-aix.org/api")
SESSION_KEY = os.environ["SESSION_KEY"]

# Session keys encode "session_id:player:signature" as base64, so the
# session ID and player can be read straight off the key you copied from
# the UI without a separate lookup.
session_id, player, _ = (
    base64.urlsafe_b64decode(SESSION_KEY.removeprefix("nks_") + "==")
    .decode()
    .split(":")
)

agent = PrisonersDilemmaAgent(
    player=player,
    player_token=SESSION_KEY,
    session_id=session_id,
    arena_url=ARENA_URL,
    llm_config=LLMConfig(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"]),
)

results = agent.run_sync()
print(f"Winner: {results['winner']} — scores: {results['scores']}")
