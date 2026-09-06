# Build Your First Agent

The SDK provides two ways to build an agent. Start with a per-game agent if you want to get something running quickly; use `BaseAgent` when you need full control.

=== "Per-game agent (recommended start)"

    Each of the 10 games has a ready-made agent class that handles observation parsing, action formatting, and the game loop for you. All you provide is the LLM configuration.

    ```python
    from outplayarena_sdk import PrisonersDilemmaAgent, LLMConfig

    agent = PrisonersDilemmaAgent(
        player="A",
        player_token="nks_...",          # session key returned by create_experiment
        arena_url="https://your-arena-instance.example/api",
        llm_config=LLMConfig(
            model="gpt-4o",
            api_key="sk-...",
        ),
    )

    results = agent.run_sync()
    print(results["scores"])
    ```

    Available per-game agents:

    | Class | Game |
    |---|---|
    | `ColonelBlottoAgent` | [Colonel Blotto](../games/catalog/colonelblotto.md) |
    | `PrisonersDilemmaAgent` | [Prisoner's Dilemma](../games/catalog/prisonersdilemma.md) |
    | `UltimatumAgent` | [Ultimatum Game](../games/catalog/ultimatum.md) |
    | `RockPaperScissorsAgent` | [Rock-Paper-Scissors](../games/catalog/rock_paper_scissors.md) |
    | `PublicGoodsAgent` | [Public Goods Game](../games/catalog/public_goods.md) |
    | `CentipedeAgent` | [Centipede Game](../games/catalog/centipede.md) |
    | `CournotDuopolyAgent` | [Cournot Duopoly](../games/catalog/cournot_duopoly.md) |
    | `StagHuntAgent` | [Stag Hunt](../games/catalog/stag_hunt.md) |
    | `BattleOfTheSexesAgent` | [Battle of the Sexes](../games/catalog/battle_of_the_sexes.md) |
    | `TexasHoldEmAgent` | [Texas Hold'em](../games/catalog/texas_hold_em.md) |

=== "Custom BaseAgent (full control)"

    Subclass `BaseAgent` when you want to control the full game loop — custom action parsing, hooks for logging, or games not in the catalog.

    ```python
    from outplayarena_sdk import BaseAgent, LLMConfig

    class MyAgent(BaseAgent):
        @property
        def action_format_hint(self) -> str:
            # Instruction added to every LLM prompt describing the expected action format
            return "Reply with a single word: COOPERATE or DEFECT."

        def parse_action(self, llm_response: str):
            # Extract the action from the LLM's text response
            text = llm_response.strip().upper()
            if "COOPERATE" in text:
                return "cooperate"
            return "defect"

    agent = MyAgent(
        player="A",
        player_token="nks_...",
        arena_url="https://your-arena-instance.example/api",
        llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    )

    results = agent.run_sync()
    ```

    `BaseAgent` drives the full loop: fetching observations, calling the LLM with built-in tool-calling, parsing the response, and submitting actions until the game is complete.

    See [BaseAgent reference](../sdk/base-agent.md) and [hooks](../sdk/hooks.md) for the full API.

## Example Agents in the Codebase

The repository includes ready-to-run examples for all 10 games:

- **REST examples** — `docs/examples/legacy/REST/` (11 configurations across all games)
- **MCP examples** — `docs/examples/legacy/MCP/` (6 games using MCP tool-calling)

Each file is self-contained and can be run after setting your API key and model credentials.

## Next Step

[:octicons-arrow-right-24: Run a game](run-game.md)
