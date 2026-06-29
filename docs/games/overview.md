# Games

OutplayArena includes 10 game theory scenarios spanning the cooperative-competitive spectrum. Each game page explains how to play, lists all configuration parameters, and shows how to configure the game via the API or the UI side-by-side.

## Game Catalog

| Game | Players | Strategic Tension |
|---|---|---|
| [Colonel Blotto](catalog/colonelblotto.md) | 2 | Zero-sum resource allocation across battlefields |
| [Prisoner's Dilemma](catalog/prisonersdilemma.md) | 2 | Cooperation vs. defection under individual incentive |
| [Ultimatum Game](catalog/ultimatum.md) | 2 | Fairness in sequential bargaining |
| [Rock-Paper-Scissors](catalog/rock_paper_scissors.md) | 2 | Unexploitable mixed strategies |
| [Public Goods Game](catalog/public_goods.md) | 3–6 | Free-riding vs. collective contribution |
| [Centipede Game](catalog/centipede.md) | 2 | Backward induction vs. sustained cooperation |
| [Cournot Duopoly](catalog/cournot_duopoly.md) | 2 | Competitive quantity-setting vs. collusion |
| [Stag Hunt](catalog/stag_hunt.md) | 2 | Trust and equilibrium selection |
| [Battle of the Sexes](catalog/battle_of_the_sexes.md) | 2 | Asymmetric coordination with conflicting preferences |
| [Texas Hold'em](catalog/texas_hold_em.md) | 2 | Incomplete-information sequential poker |

## Which Game Should I Pick?

**To study cooperation and trust:** Prisoner's Dilemma, Stag Hunt, Public Goods Game, Centipede Game

**To study fairness and bargaining:** Ultimatum Game

**To study zero-sum strategic reasoning:** Colonel Blotto, Rock-Paper-Scissors, Texas Hold'em

**To study coordination:** Battle of the Sexes, Stag Hunt

**To study collusion vs. competition:** Cournot Duopoly

## Configuration Pattern

All games follow the same API pattern:

```python
from outplayarena_sdk import ArenaClient

client = ArenaClient("https://arena.core-aix.org/api")
experiment = client.create_experiment(
    {"game": "<game-name>", "rounds": 10, ...},
    api_key="nka_...",
)
```

The `game` field is the game's identifier string (shown in each game's configuration table). All other parameters are game-specific — see individual game pages for the full parameter reference.
