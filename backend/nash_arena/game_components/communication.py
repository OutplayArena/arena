from dataclasses import dataclass, field
from typing import Any
import time
import uuid


@dataclass
class PlayerMessage:
    from_player: str
    to_player: str | None
    content: str
    round_number: int
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "from_player": self.from_player,
            "to_player": self.to_player,
            "content": self.content,
            "round_number": self.round_number,
            "timestamp": self.timestamp,
        }


@dataclass
class CommunicationConfig:
    enabled: bool = True
    mode: str = "both"
    max_messages_per_round: int = 3
    max_message_length: int = 500

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "max_messages_per_round": self.max_messages_per_round,
            "max_message_length": self.max_message_length,
        }

    @classmethod
    def default(cls) -> "CommunicationConfig":
        return cls()

    @classmethod
    def disabled(cls) -> "CommunicationConfig":
        return cls(enabled=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CommunicationConfig":
        if not data:
            return cls.default()
        return cls(
            enabled=data.get("enabled", True),
            mode=data.get("mode", "both"),
            max_messages_per_round=data.get("max_messages_per_round", 3),
            max_message_length=data.get("max_message_length", 500),
        )
