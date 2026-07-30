"""
Robust RabbitMQ connection factory.

Builds an aio_pika RobustConnection with reconnect/close callbacks wired to a
ConsumerState. Reconnection after the initial successful connect is handled by
aio-pika itself (RobustChannel/RobustQueue re-register consumers automatically);
callers only need an outer retry loop for the initial connection.

Also used by service-specific consumers and pollers that need their own
connection outside the request/response pipeline.
"""

import logging

import aio_pika

from integration_framework.messaging.state import ConsumerState
from integration_framework.settings import FrameworkSettings

_logger = logging.getLogger(__name__)


async def create_robust_connection(
    settings: FrameworkSettings,
    state: ConsumerState | None = None,
    logger: logging.Logger | None = None,
    name: str = "consumer",
) -> aio_pika.RobustConnection:
    logger = logger or _logger

    logger.info(
        "%s connecting to RabbitMQ at %s:%s vhost=%s",
        name, settings.rabbitmq_host, settings.rabbitmq_port, settings.rabbitmq_vhost,
    )

    connection: aio_pika.RobustConnection = await aio_pika.connect_robust(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        login=settings.rabbitmq_user,
        password=settings.rabbitmq_password,
        virtualhost=settings.rabbitmq_vhost,
        heartbeat=settings.rabbitmq_heartbeat,
        timeout=settings.rabbitmq_connection_timeout,
    )

    def _on_reconnect(_conn: aio_pika.RobustConnection) -> None:
        logger.info("%s reconnected to RabbitMQ", name)
        if state:
            state.mark_connected()

    def _on_close(_sender, exc: BaseException | None = None) -> None:
        if exc:
            logger.warning("%s connection lost: %s. Waiting for reconnect...", name, exc)
            if state:
                state.mark_disconnected(str(exc))

    connection.reconnect_callbacks.add(_on_reconnect)
    connection.close_callbacks.add(_on_close)

    return connection
