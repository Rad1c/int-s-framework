"""
Client-to-server request/response consumer.

Consumes messages from the per-service request queue (bound to the shared
fanout request exchange, so every integration service receives its own copy of
each request), dispatches them by serviceType + payload.messageType through the
HandlerRegistry, and publishes the standard response envelope to the response
queue with the same X-Device-Id / X-Request-Id correlation headers.

Ack/nack semantics:
- invalid JSON            -> error envelope published, message acked
- serviceType mismatch    -> no response published, message acked
- handler error/exception -> error envelope published, message acked
- infrastructure failure  -> message nacked (requeue=False)
"""

import asyncio
import json
import logging
from typing import Any

import aio_pika
import aio_pika.abc

from integration_framework.envelope import error
from integration_framework.handlers import HandlerRegistry, route_payload
from integration_framework.integration_log_repository import IntegrationLogRepository
from integration_framework.messaging.connection import create_robust_connection
from integration_framework.messaging.publisher import publish_response
from integration_framework.messaging.state import ConsumerState
from integration_framework.settings import FrameworkSettings

_logger = logging.getLogger(__name__)


class RequestConsumer:
    def __init__(
        self,
        settings: FrameworkSettings,
        registry: HandlerRegistry,
        context: Any,
        audit_repository: IntegrationLogRepository,
        state: ConsumerState | None = None,
        logger: logging.Logger | None = None,
    ):
        self.settings = settings
        self.registry = registry
        self.context = context
        self.audit_repository = audit_repository
        self.state = state if state is not None else ConsumerState()
        self.logger = logger or _logger

    async def run(self) -> None:
        """Connect and consume until cancelled. Initial connection failures are
        retried with exponential backoff; reconnects after a successful connect
        are handled by aio-pika's RobustConnection."""
        settings = self.settings
        delay = settings.rabbitmq_initial_retry_delay
        attempt = 0

        while True:
            attempt += 1
            try:
                await self._connect_and_consume()
                delay = settings.rabbitmq_initial_retry_delay
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.state.mark_disconnected(str(e))
                if settings.rabbitmq_max_retry_attempts > 0 and attempt >= settings.rabbitmq_max_retry_attempts:
                    self.logger.error(
                        "Request consumer failed to connect after %d attempts. Giving up.", attempt
                    )
                    raise
                self.logger.error(
                    "Request consumer failed to connect: %s. Retrying in %ss...", e, delay
                )
                await asyncio.sleep(delay)
                delay = min(delay * settings.rabbitmq_retry_backoff_multiplier, settings.rabbitmq_max_retry_delay)

    async def _connect_and_consume(self) -> None:
        settings = self.settings
        connection = await create_robust_connection(
            settings, self.state, self.logger, name="Request consumer"
        )

        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=settings.consumer_prefetch_count)

            request_exchange = await channel.declare_exchange(
                settings.rabbitmq_request_topic, aio_pika.ExchangeType.FANOUT, durable=True
            )
            request_queue = await channel.declare_queue(settings.rabbitmq_request_queue, durable=True)
            await request_queue.bind(request_exchange)
            # Ensure the response queue exists so publishes are not dropped.
            await channel.declare_queue(settings.rabbitmq_response_topic, durable=True)

            await request_queue.consume(lambda message: self._on_request(channel, message))

            self.state.mark_connected()
            self.logger.info(
                "Request consumer started — request exchange: %s | request queue: %s | response queue: %s",
                settings.rabbitmq_request_topic,
                settings.rabbitmq_request_queue,
                settings.rabbitmq_response_topic,
            )

            await asyncio.Future()  # runs until cancelled; reconnects handled by connect_robust

    async def _on_request(
        self,
        channel: aio_pika.abc.AbstractChannel,
        message: aio_pika.abc.AbstractIncomingMessage,
    ) -> None:
        headers = message.headers or {}
        device_id = headers.get("X-Device-Id")
        request_id = headers.get("X-Request-Id")
        try:
            self.logger.info(
                "Received request message (X-Device-Id=%s, X-Request-Id=%s)", device_id, request_id
            )
            try:
                message_data = json.loads(message.body.decode("utf-8"))
            except json.JSONDecodeError as e:
                self.logger.error("Invalid JSON in request message: %s", e)
                await publish_response(
                    channel, self.settings.rabbitmq_response_topic,
                    error(f"Invalid JSON: {e}"), device_id, request_id, self.logger,
                )
                await message.ack()
                return

            response = await self.process(message_data, device_id, request_id)

            # None => message targets a different serviceType; ack without responding.
            if response is not None:
                await publish_response(
                    channel, self.settings.rabbitmq_response_topic,
                    response, device_id, request_id, self.logger,
                )

            await message.ack()
            self.logger.info("Request message acknowledged (X-Request-Id=%s)", request_id)
        except Exception:
            self.logger.exception("Error processing request message")
            await message.nack(requeue=False)
            self.logger.info("Request message nacked (requeue=False)")

    async def process(
        self, message_data: dict, device_id: str | None = None, request_id: str | None = None
    ):
        """Route a decoded message through the handler registry. Also used by
        the debug controller so HTTP simulation shares the exact same path."""
        return await route_payload(
            message_data, self.registry, self.settings.service_type,
            self.context, self.audit_repository, self.logger, device_id, request_id,
        )
