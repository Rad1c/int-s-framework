"""
Minimal integration service built on integration-service-framework.
Real services keep their external HTTP/SOAP/gRPC client beside their handlers
and pass it to IntegrationService as context.

Run a local RabbitMQ first:
    docker compose -f docker-compose.rabbitmq.yml up -d

Then start the service (from the repo root, with the package installed):
    set APP_ENV=development
    python examples/echo_service/main.py

Smoke test via the debug endpoint:
    curl -X POST http://localhost:8080/debug/simulate-request \
      -H "Content-Type: application/json" \
      -H "X-Device-Id: dev-1" -H "X-Request-Id: req-1" \
      -d '{"serviceType": "echo_service", "payload": {"messageType": "Echo", "message": {"text": "hello"}}}'

Or publish the same JSON to the 'requests' exchange in the RabbitMQ management
UI (http://localhost:15672) with X-Device-Id / X-Request-Id headers and watch
the response envelope arrive on the 'responses' queue.
"""

from integration_framework import FrameworkSettings, HandlerRegistry, IntegrationService

registry = HandlerRegistry()


class Settings(FrameworkSettings):
    service_name: str = "Echo Integration Service"
    service_type: str = "echo_service"
    rabbitmq_request_queue: str = "requests.echo"


@registry.handler("Echo")
async def handle_echo(payload, context, logger, device_id, request_id, audit_repository):
    message = payload.get("message") or {}
    logger.info(
        "Echo handler - message=%s, X-Device-Id=%s, X-Request-Id=%s",
        message,
        device_id,
        request_id,
    )
    return True, {"data": message}, ""


def main():
    service = IntegrationService(settings=Settings(), registry=registry)
    service.run()


if __name__ == "__main__":
    main()
