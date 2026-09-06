"""Per-game :class:`BaseAgent` subclasses, one per game in ``games/games/core/``.

Import the class for the game you want to play::

    from outplayarena_sdk.agents.games import (
        ColonelBlottoAgent,
        UltimatumAgent,
        PrisonersDilemmaAgent,
        ...
    )

Or rely on the top-level re-exports and the ``quick_play`` helper::

    from outplayarena_sdk import quick_play
    results = quick_play(game="colonelblotto", agents={...})
"""
from outplayarena_sdk.agents.games.battle_of_the_sexes import (
    BattleOfTheSexesAgent,
)
from outplayarena_sdk.agents.games.centipede import CentipedeAgent
from outplayarena_sdk.agents.games.chicken_game import ChickenGameAgent
from outplayarena_sdk.agents.games.colonelblotto import ColonelBlottoAgent
from outplayarena_sdk.agents.games.cournot_duopoly import CournotDuopolyAgent
from outplayarena_sdk.agents.games.prisonersdilemma import (
    PrisonersDilemmaAgent,
)
from outplayarena_sdk.agents.games.public_goods import PublicGoodsAgent
from outplayarena_sdk.agents.games.rock_paper_scissors import (
    RockPaperScissorsAgent,
)
from outplayarena_sdk.agents.games.stag_hunt import StagHuntAgent
from outplayarena_sdk.agents.games.texas_hold_em import TexasHoldEmAgent
from outplayarena_sdk.agents.games.ultimatum import UltimatumAgent
from outplayarena_sdk.agents.games.vickrey_auction import VickreyAuctionAgent


__all__ = [
    "BattleOfTheSexesAgent",
    "CentipedeAgent",
    "ChickenGameAgent",
    "ColonelBlottoAgent",
    "CournotDuopolyAgent",
    "PrisonersDilemmaAgent",
    "PublicGoodsAgent",
    "RockPaperScissorsAgent",
    "StagHuntAgent",
    "TexasHoldEmAgent",
    "UltimatumAgent",
    "VickreyAuctionAgent",
]
