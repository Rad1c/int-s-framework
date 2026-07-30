from unittest.mock import AsyncMock

from integration_framework.handlers import HandlerRegistry
from integration_framework.messaging.request_consumer import RequestConsumer
from integration_framework.messaging.state import ConsumerState
from tests.conftest import make_channel, make_incoming_message, make_settings, published_envelope


async def echo_handler(payload, context, logger):
    return True, {"data": payload.get("message")}, ""


def make_consumer(handlers=None, context=None):
    settings = make_settings()
    registry = HandlerRegistry(handlers if handlers is not None else {"Echo": echo_handler})
    return RequestConsumer(settings, registry, context, ConsumerState())


def valid_request(message=None, service_type="test_service"):
    return {"serviceType": service_type, "payload": {"messageType": "Echo", "message": message or {}}}


async def test_valid_message_publishes_response_and_acks():
    consumer = make_consumer()
    channel = make_channel()
    message = make_incoming_message(valid_request({"text": "hi"}))

    await consumer._on_request(channel, message)

    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()
    assert published_envelope(channel) == {
        "success": 0, "payload": {"data": {"text": "hi"}}, "error_message": ""
    }


async def test_response_routed_to_response_queue_with_correlation_headers():
    consumer = make_consumer()
    channel = make_channel()
    message = make_incoming_message(valid_request(), device_id="dev-42", request_id="req-42")

    await consumer._on_request(channel, message)

    call = channel.default_exchange.publish.call_args
    assert call.kwargs["routing_key"] == consumer.settings.rabbitmq_response_topic
    published = call.args[0]
    assert published.headers == {"X-Device-Id": "dev-42", "X-Request-Id": "req-42"}


async def test_invalid_json_publishes_error_and_acks():
    consumer = make_consumer()
    channel = make_channel()
    message = make_incoming_message("this is not json")

    await consumer._on_request(channel, message)

    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()
    envelope = published_envelope(channel)
    assert envelope["success"] == 1
    assert "Invalid JSON" in envelope["error_message"]


async def test_other_service_type_acks_without_response():
    consumer = make_consumer()
    channel = make_channel()
    message = make_incoming_message(valid_request(service_type="other_service"))

    await consumer._on_request(channel, message)

    message.ack.assert_awaited_once()
    channel.default_exchange.publish.assert_not_awaited()


async def test_unknown_message_type_publishes_error_envelope():
    consumer = make_consumer(handlers={})
    channel = make_channel()
    message = make_incoming_message(valid_request())

    await consumer._on_request(channel, message)

    message.ack.assert_awaited_once()
    envelope = published_envelope(channel)
    assert envelope["success"] == 1
    assert "Unknown messageType" in envelope["error_message"]


async def test_handler_exception_publishes_error_envelope():
    async def failing(payload, context, logger):
        raise RuntimeError("kaboom")

    consumer = make_consumer(handlers={"Echo": failing})
    channel = make_channel()
    message = make_incoming_message(valid_request())

    await consumer._on_request(channel, message)

    message.ack.assert_awaited_once()
    envelope = published_envelope(channel)
    assert envelope["success"] == 1
    assert "kaboom" in envelope["error_message"]


async def test_publish_failure_nacks_without_requeue():
    consumer = make_consumer()
    channel = make_channel()
    channel.default_exchange.publish = AsyncMock(side_effect=ConnectionError("broker gone"))
    message = make_incoming_message(valid_request())

    await consumer._on_request(channel, message)

    message.ack.assert_not_awaited()
    message.nack.assert_awaited_once_with(requeue=False)


async def test_missing_headers_handled():
    consumer = make_consumer()
    channel = make_channel()
    message = make_incoming_message(valid_request(), device_id=None, request_id=None)

    await consumer._on_request(channel, message)

    message.ack.assert_awaited_once()
    published = channel.default_exchange.publish.call_args.args[0]
    # aio_pika normalizes headers=None to {}; either way no correlation headers are set.
    assert not published.headers


async def test_process_returns_envelope_directly():
    # Used by the debug controller: same path, no publish.
    consumer = make_consumer()
    response = await consumer.process(valid_request({"text": "hi"}), "dev-1", "req-1")
    assert response == {"success": 0, "payload": {"data": {"text": "hi"}}, "error_message": ""}


async def test_process_returns_none_for_other_service():
    consumer = make_consumer()
    response = await consumer.process(valid_request(service_type="other_service"))
    assert response is None
