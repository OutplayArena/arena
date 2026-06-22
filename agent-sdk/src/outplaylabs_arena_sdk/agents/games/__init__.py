"""Per-game :class:`BaseAgent` subclasses, one per game in ``games/games/core/``.

Import the class for the game you want to play::

    from outplaylabs_arena_sdk.agents.games import (
        ColonelBlottoAgent,
        UltimatumAgent,
        PrisonersDilemmaAgent,
        ...
    )

Or rely on the top-level re-exports and the ``quick_play`` helper::

    from outplaylabs_arena_sdk import quick_play
    results = quick_play(game="colonelblotto", agents={...})
"""
from outplaylabs_arena_sdk.agents.games.battle_of_the_sexes import (
    BattleOfTheSexesAgent,
)
from outplaylabs_arena_sdk.agents.games.centipede import CentipedeAgent
from outplaylabs_arena_sdk.agents.games.colonelblotto import ColonelBlottoAgent
from outplaylabs_arena_sdk.agents.games.cournot_duopoly import CournotDuopolyAgent
from outplaylabs_arena_sdk.agents.games.prisonersdilemma import (
    PrisonersDilemmaAgent,
)
from outplaylabs_arena_sdk.agents.games.public_goods import PublicGoodsAgent
from outplaylabs_arena_sdk.agents.games.rock_paper_scissors import (
    RockPaperScissorsAgent,
)
from outplaylabs_arena_sdk.agents.games.stag_hunt import StagHuntAgent
from outplaylabs_arena_sdk.agents.games.texas_hold_em import TexasHoldEmAgent
from outplaylabs_arena_sdk.agents.games.ultimatum import UltimatumAgent


__all__ = [
    "BattleOfTheSexesAgent",
    "CentipedeAgent",
    "ColonelBlottoAgent",
    "CournotDuopolyAgent",
    "PrisonersDilemmaAgent",
    "PublicGoodsAgent",
    "RockPaperScissorsAgent",
    "StagHuntAgent",
    "TexasHoldEmAgent",
    "UltimatumAgent",
]
