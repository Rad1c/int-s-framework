"""Health check routes with RabbitMQ consumer status."""

import logging

from fastapi import FastAPI

from integration_framework.messaging.state import ConsumerState

_logger = logging.getLogger(__name__)


def register_health_routes(app: FastAPI, state: ConsumerState, service_name: str) -> None:
    @app.get("/health")
    async def health():
        status = "ok" if state.connected else "degraded"
        return {
            "status": status,
            "service": "running",
            "rabbitmq": {
                "connected": state.connected,
                "state": state.state,
                "last_connected_at": (
                    state.last_connected_at.isoformat() if state.last_connected_at else None
                ),
                "last_error": state.last_error,
            },
        }

    @app.get("/")
    async def root():
        return {"status": "ok", "service": service_name}
