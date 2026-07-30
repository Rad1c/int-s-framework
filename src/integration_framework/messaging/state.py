"""Connection state shared between a consumer and the health endpoint."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ConsumerState:
    connected: bool = False
    last_connected_at: Optional[datetime] = None
    last_error: Optional[str] = None

    @property
    def state(self) -> str:
        return "connected" if self.connected else "disconnected"

    def mark_connected(self) -> None:
        self.connected = True
        self.last_connected_at = datetime.now(timezone.utc)
        self.last_error = None

    def mark_disconnected(self, error: str) -> None:
        self.connected = False
        self.last_error = error
