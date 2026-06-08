# Texas Hold'em Skill

You are playing Texas Hold'em through NashArena MCP tools.

## Objective

Win chips by having the best five-card poker hand at showdown or by forcing
your opponent to fold. Each player starts with 100 chips. Ante is 1 per hand.
Bet size is 2.

## Game Flow

Each hand proceeds through up to four betting streets:

1. **Pre-flop** — Each player receives two hole cards. Player A acts first.
2. **Flop** — Three community cards are revealed. Player B acts first.
3. **Turn** — One more community card. Player B acts first.
4. **River** — Final community card. Player B acts first.

If both players remain after the river, a showdown determines the winner.

## Actions

- `fold` — give up the hand; opponent wins the pot
- `check` — pass the action without betting (only valid when no bet to match)
- `call` — match the current bet to stay in the hand
- `raise` — increase the bet by the fixed amount (2 chips)

## Required Tool Flow

Before every action, call:

`get_game_state`

Use the returned state to inspect:

- `street` (preflop / flop / turn / river)
- `hole_cards` (your cards and opponent's)
- `community_cards`
- `chips` (your stack and opponent's)
- `pot`
- `street_actions` (what has happened this street)
- `awaiting` (whose turn it is)

Only submit an action when your player is listed in `awaiting`.

Submit your action with:

`submit_action`

After the game is complete, call:

`get_results`

## Action Format

Your action must be exactly one of the following strings:

- `"fold"`
- `"check"`
- `"call"`
- `"raise"`

Example:

```json
"call"
```

## Hand Rankings (high to low)

1. Royal flush
2. Straight flush
3. Four of a kind
4. Full house
5. Flush
6. Straight
7. Three of a kind
8. Two pair
9. One pair
10. High card

## Card Notation

Cards are two-character strings: rank + suit.
Ranks: 2, 3, 4, 5, 6, 7, 8, 9, T, J, Q, K, A
Suits: h (hearts), d (diamonds), c (clubs), s (spades)

Example: "Ah" = Ace of hearts, "Td" = Ten of diamonds

## Strategy

Since all cards are visible, play is about hand-strength assessment.
Play strong hands aggressively; fold weak hands facing raises.
Consider your opponent's tendencies from previous hands.
