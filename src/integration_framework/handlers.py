"""
Handler registry and message routing.

A handler maps a payload.messageType to service business logic:

    async def handle_redeem_ticket(
        payload, context, logger, device_id, request_id, audit_repository
    ) -> tuple[bool, dict, str]:
        ...
        return True, {"data": data}, ""

`context` is the service-specific dependency passed to IntegrationService
(an API client, a service layer object, ...). `route_payload` dispatches an
inbound message to the right handler and wraps the result in the standard
response envelope (see envelope.py).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from integration_framework.envelope import envelope, error
from integration_framework.integration_log_repository import IntegrationLogRepository

Handler = Callable[
    [
        dict[str, Any],
        Any,
        logging.Logger,
        str | None,
        str | None,
        IntegrationLogRepository,
    ],
    Awaitable[tuple[bool, dict[str, Any], str]],
]

_logger = logging.getLogger(__name__)


class HandlerRegistry:
    """Maps messageType -> handler. Register via decorator or directly:

    registry = HandlerRegistry()

    @registry.handler("RedeemTicket")
    async def handle_redeem_ticket(
        payload, context, logger, device_id, request_id, audit_repository
    ): ...

    # or bulk-register an existing MESSAGE_HANDLERS dict:
    registry.update(MESSAGE_HANDLERS)
    """

    def __init__(self, handlers: dict[str, Handler] | None = None):
        self._handlers: dict[str, Handler] = dict(handlers or {})

    def handler(self, message_type: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            self.register(message_type, fn)
            return fn
        return decorator

    def register(self, message_type: str, fn: Handler) -> None:
        if message_type in self._handlers:
            raise ValueError(f"Handler for messageType {message_type!r} already registered")
        self._handlers[message_type] = fn

    def update(self, handlers: dict[str, Handler]) -> None:
        for message_type, fn in handlers.items():
            self.register(message_type, fn)

    def get(self, message_type: str) -> Handler | None:
        return self._handlers.get(message_type)

    def __contains__(self, message_type: str) -> bool:
        return message_type in self._handlers

    def __len__(self) -> int:
        return len(self._handlers)


async def route_payload(
    message_data: dict[str, Any],
    registry: HandlerRegistry,
    expected_service_type: str,
    context: Any,
    audit_repository: IntegrationLogRepository,
    logger: logging.Logger | None = None,
    device_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Routes an inbound client-to-server message to the matching handler.

    Returns the standard response envelope, or None when the message targets a
    different serviceType (so the caller does not publish a response).
    """
    logger = logger or _logger

    service_type = message_data.get("serviceType")
    payload = message_data.get("payload") or {}
    message_type = payload.get("messageType")

    logger.info(
        "Processing message - serviceType=%s, messageType=%s, X-Device-Id=%s, X-Request-Id=%s",
        service_type, message_type, device_id, request_id,
    )

    if service_type != expected_service_type:
        logger.debug("Ignoring message with serviceType=%r (X-Request-Id=%s)", service_type, request_id)
        return None

    handler = registry.get(message_type)
    if handler is None:
        error_msg = f"Unknown messageType: {message_type!r}"
        logger.warning(error_msg)
        return error(error_msg)

    try:
        success, response_data, error_message = await handler(
            payload, context, logger, device_id, request_id, audit_repository
        )
    except Exception as e:
        logger.exception("Error processing messageType=%s", message_type)
        return error(f"Processing error: {e}")

    logger.info(
        "Message processing completed - messageType=%s, X-Request-Id=%s, success=%s",
        message_type, request_id, success,
    )
    return envelope(success, response_data, error_message)
