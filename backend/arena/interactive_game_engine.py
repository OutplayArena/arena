"""Base class for games that support interactive human play."""
from __future__ import annotations

from typing import Any

from arena.game_engine import GameEngine


class InteractiveGameEngine(GameEngine):
    """Base class for games that support interactive human play.
    
    This extends GameEngine with methods for:
    - Defining action schemas for human input
    - Formatting and validating human actions
    - Providing UI metadata for frontend rendering
    - Listing available AI agents for the game
    """

    def human_action_schema(self, config: Any) -> dict:
        """Return JSON Schema for valid human actions.
        
        Args:
            config: Game configuration
            
        Returns:
            JSON Schema dict describing valid action format
        """
        raise NotImplementedError("Subclass must implement human_action_schema")

    def format_human_action(self, raw_action: Any, config: Any) -> Any:
        """Format raw human input into game action format.
        
        Args:
            raw_action: Raw input from human (could be string, dict, etc.)
            config: Game configuration
            
        Returns:
            Formatted action suitable for apply_action()
        """
        raise NotImplementedError("Subclass must implement format_human_action")

    def validate_human_action(
        self, state: Any, player: str, action: Any, config: Any
    ) -> bool:
        """Validate a formatted human action.
        
        Args:
            state: Current game state
            player: Player ID (e.g., "A" or "B")
            action: Formatted action
            config: Game configuration
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If action is invalid
        """
        # Default implementation uses validate_action
        return self.validate_action(action)

    def ui_metadata(self, config: Any) -> dict:
        """Return UI metadata for frontend rendering.
        
        Args:
            config: Game configuration
            
        Returns:
            Dict with UI hints like input_type, choices, layout, etc.
        """
        return {
            "input_type": "text",
            "layout": "default",
        }

    def interactive_public_state(
        self, state: Any, config: Any, session_id: str, config_hash: str, player: str | None = None
    ) -> dict:
        """Return public state with player-specific context.
        
        Args:
            state: Current game state
            config: Game configuration
            session_id: Session ID
            config_hash: Config hash
            player: Optional player ID for player-specific info
            
        Returns:
            Public state dict
        """
        # Default implementation just returns base public state
        return self.public_state(state, config, session_id, config_hash)

    def get_available_agents(self, config: Any) -> list[dict]:
        """Return list of available AI agents for this game.

        Args:
            config: Game configuration

        Returns:
            List of dicts with id, label, description for each agent
        """
        return []

    def forfeit_round(self, state: Any, player: str) -> Any:
        """Handle a player forfeiting the current round.

        The default raises NotImplementedError. Games that can be forfeited
        must override this method.

        Args:
            state: Current game state
            player: Player ID forfeiting this round

        Raises:
            NotImplementedError: If this game does not support forfeit
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement forfeit_round(). "
            "Override this method to support mid-round forfeiture."
        )
