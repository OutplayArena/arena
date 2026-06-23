"""Per-game agent subclasses for the OutplayLabs Arena SDK.

Each module exposes an :class:`BaseAgent` subclass that knows the action
format for one game in ``games/games/core/``. Subclasses override
:meth:`parse_action` and :meth:`action_format_hint`; everything else
(the autonomous loop, hooks, seeding, tool-calling) is inherited from
:class:`BaseAgent`.

The 10 games currently supported:

    battle_of_the_sexes   centipede           colonelblotto
    cournot_duopoly       prisonersdilemma    public_goods
    rock_paper_scissors   stag_hunt           texas_hold_em
    ultimatum

Re-exports live in :mod:`outplaylabs_arena_sdk.agents.games`.
"""
