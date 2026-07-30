"""Connection state shared between a consumer and the health endpoint."""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class ConsumerState:
    connected: bool = False
    last_connected_at: datetime | None = None
    last_error: str | None = None

    @property
    def state(self) -> str:
        return "connected" if self.connected else "disconnected"

    def mark_connected(self) -> None:
        self.connected = True
        self.last_connected_at = datetime.now(UTC)
        self.last_error = None

    def mark_disconnected(self, error: str) -> None:
        self.connected = False
        self.last_error = error
