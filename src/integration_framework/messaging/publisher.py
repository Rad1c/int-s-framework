"""Publishing of response envelopes with correlation headers."""

import json
import logging
from typing import Any, Dict, Optional

import aio_pika

_logger = logging.getLogger(__name__)


def correlation_headers(device_id: Optional[str], request_id: Optional[str]) -> Dict[str, str]:
    headers = {}
    if device_id is not None:
        headers["X-Device-Id"] = device_id
    if request_id is not None:
        headers["X-Request-Id"] = request_id
    return headers


async def publish_response(
    channel: aio_pika.abc.AbstractChannel,
    response_queue: str,
    response: Dict[str, Any],
    device_id: Optional[str] = None,
    request_id: Optional[str] = None,
    logger: logging.Logger = None,
) -> None:
    """Publish a response envelope to the response queue, echoing the inbound
    message's X-Device-Id / X-Request-Id correlation headers."""
    logger = logger or _logger

    headers = correlation_headers(device_id, request_id)
    logger.info(
        "Publishing response to queue %s (X-Device-Id=%s, X-Request-Id=%s, success=%s)",
        response_queue, device_id, request_id, response.get("success"),
    )
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(response).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers or None,
        ),
        routing_key=response_queue,
    )
