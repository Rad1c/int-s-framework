import logging

import pytest

from integration_framework.handlers import HandlerRegistry, route_payload

_logger = logging.getLogger("test")


async def echo_handler(payload, context, logger):
    return True, {"data": payload.get("message")}, ""


async def failing_handler(payload, context, logger):
    raise RuntimeError("kaboom")


async def business_error_handler(payload, context, logger):
    return False, {}, "not found"


def request(message_type: str, message: dict | None = None, service_type: str = "test_service") -> dict:
    return {"serviceType": service_type, "payload": {"messageType": message_type, "message": message or {}}}


def test_register_and_get():
    registry = HandlerRegistry()
    registry.register("Echo", echo_handler)
    assert registry.get("Echo") is echo_handler
    assert "Echo" in registry
    assert len(registry) == 1


def test_decorator_registration():
    registry = HandlerRegistry()

    @registry.handler("Echo")
    async def my_handler(payload, context, logger):
        return True, {}, ""

    assert registry.get("Echo") is my_handler


def test_duplicate_registration_raises():
    registry = HandlerRegistry()
    registry.register("Echo", echo_handler)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("Echo", echo_handler)


def test_update_from_dict():
    # Existing services expose MESSAGE_HANDLERS dicts; they must plug in directly.
    registry = HandlerRegistry()
    registry.update({"A": echo_handler, "B": business_error_handler})
    assert len(registry) == 2


def test_init_from_dict():
    registry = HandlerRegistry({"A": echo_handler})
    assert registry.get("A") is echo_handler


async def test_route_payload_success():
    registry = HandlerRegistry({"Echo": echo_handler})
    response = await route_payload(
        request("Echo", {"text": "hi"}), registry, "test_service", None, _logger, "dev-1", "req-1"
    )
    assert response == {"success": 0, "payload": {"data": {"text": "hi"}}, "error_message": ""}


async def test_route_payload_wrong_service_type_returns_none():
    registry = HandlerRegistry({"Echo": echo_handler})
    response = await route_payload(
        request("Echo", service_type="other_service"), registry, "test_service", None, _logger
    )
    assert response is None


async def test_route_payload_unknown_message_type():
    registry = HandlerRegistry()
    response = await route_payload(request("Nope"), registry, "test_service", None, _logger)
    assert response["success"] == 1
    assert "Unknown messageType" in response["error_message"]


async def test_route_payload_handler_exception():
    registry = HandlerRegistry({"Fail": failing_handler})
    response = await route_payload(request("Fail"), registry, "test_service", None, _logger)
    assert response["success"] == 1
    assert "kaboom" in response["error_message"]


async def test_route_payload_business_error():
    registry = HandlerRegistry({"Miss": business_error_handler})
    response = await route_payload(request("Miss"), registry, "test_service", None, _logger)
    assert response == {"success": 1, "payload": {}, "error_message": "not found"}


async def test_route_payload_context_passed_to_handler():
    seen = {}

    async def handler(payload, context, logger):
        seen["context"] = context
        return True, {}, ""

    registry = HandlerRegistry({"Ctx": handler})
    sentinel = object()
    await route_payload(request("Ctx"), registry, "test_service", sentinel, _logger)
    assert seen["context"] is sentinel


async def test_route_payload_missing_payload():
    registry = HandlerRegistry({"Echo": echo_handler})
    response = await route_payload({"serviceType": "test_service"}, registry, "test_service", None, _logger)
    assert response["success"] == 1
    assert "Unknown messageType" in response["error_message"]
