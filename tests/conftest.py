import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from integration_framework.settings import FrameworkSettings


def make_settings(**overrides) -> FrameworkSettings:
    defaults = {
        "service_type": "test_service",
        "rabbitmq_request_queue": "requests.test",
    }
    defaults.update(overrides)
    return FrameworkSettings(_env_file=None, **defaults)


@pytest.fixture
def settings() -> FrameworkSettings:
    return make_settings()


def make_incoming_message(body: dict | str, device_id: str = "dev-1", request_id: str = "req-1"):
    """Fake aio_pika IncomingMessage with async ack/nack."""
    message = MagicMock()
    message.body = (json.dumps(body) if isinstance(body, dict) else body).encode("utf-8")
    message.headers = {}
    if device_id is not None:
        message.headers["X-Device-Id"] = device_id
    if request_id is not None:
        message.headers["X-Request-Id"] = request_id
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    return message


def make_channel():
    """Fake aio_pika channel capturing publishes on the default exchange."""
    channel = MagicMock()
    channel.default_exchange.publish = AsyncMock()
    return channel


def published_envelope(channel) -> dict:
    """Decode the last envelope published on the fake channel."""
    call = channel.default_exchange.publish.call_args
    message = call.args[0]
    return json.loads(message.body.decode("utf-8"))
