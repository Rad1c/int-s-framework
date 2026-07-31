# integration-service-framework

Shared foundation for Monroe integration services. The framework owns RabbitMQ
request/response flow, handler routing, response envelopes, health/debug
endpoints, common configuration, logging, lifecycle, and best-effort
PostgreSQL audit logging.

A consumer service owns only its service-specific settings, external client
(HTTP/SOAP/gRPC), and business handlers.

## Installation

Pin a released Git tag in the consumer's `requirements.txt`:

```text
integration-service-framework @ git+https://github.com/Rad1c/int-s-framework.git@v0.1.1
```

VCS installation requires `git`; install it in the Docker builder stage.
The framework requires Python 3.11+.

## Minimal service

```python
from integration_framework import FrameworkSettings, HandlerRegistry, IntegrationService


class Settings(FrameworkSettings):
    service_name: str = "Example Integration Service"
    service_type: str = "example_service"
    rabbitmq_request_queue: str = "requests.example"
    example_api_base_url: str = "https://example.test"


async def handle_query(
    payload, api_client, logger, device_id, request_id, audit_repository
):
    message = payload.get("message") or {}
    success, data, headers, _status, error = await api_client.get(
        f"/items/{message['id']}"
    )
    return success, {"data": data, "headers": headers}, error


def main() -> None:
    settings = Settings()
    api_client = ExampleApiClient(settings.example_api_base_url)
    service = IntegrationService(
        settings=settings,
        registry=HandlerRegistry({"Query": handle_query}),
        context=api_client,
        on_shutdown=[api_client.close],
    )
    service.run()
```

A runnable no-client example is in
[examples/echo_service/main.py](examples/echo_service/main.py).

## Responsibility boundary

| Framework owns | Consumer service owns |
|---|---|
| RabbitMQ connect, consume, publish, ack/nack, reconnect | External HTTP/SOAP/gRPC client |
| `serviceType` and `messageType` routing | Business handlers and endpoint paths |
| Response envelope and correlation headers | Service-specific response mapping |
| FastAPI lifecycle, `/health`, `/`, development `/debug` | Optional extra routes/tasks |
| Common settings and rotating logging | Additional service-specific settings |
| Lazy best-effort audit repository | Explicit audit calls around external requests |

Do not copy framework-owned infrastructure into consumer services.

## Handler contract

Register handlers by mapping or decorator:

```python
registry = HandlerRegistry({"Query": handle_query})

# or
registry = HandlerRegistry()

@registry.handler("Query")
async def handle_query(
    payload, context, logger, device_id, request_id, audit_repository
):
    return True, {"data": {}}, ""
```

Every handler receives:

1. `payload`: inbound `payload` object.
2. `context`: service-owned dependency passed to `IntegrationService`.
3. `logger`: configured service logger.
4. `device_id`: inbound `X-Device-Id`, or `None`.
5. `request_id`: inbound `X-Request-Id`, or `None`.
6. `audit_repository`: framework-owned `IntegrationLogRepository`.

It returns `(success: bool, payload: dict, error_message: str)`. The framework
converts that result to:

```json
{"success": 0, "payload": {}, "error_message": ""}
```

Envelope `success` is `0` for success and `1` for failure.

## Messaging behavior

- Requests arrive through the durable per-service queue bound to the shared
  fanout request exchange.
- A different `serviceType` is acknowledged without a response.
- An unknown `messageType`, invalid JSON, or handler error produces an error
  envelope.
- Successful processing publishes to the response queue with the inbound
  `X-Device-Id` and `X-Request-Id` headers, then acknowledges the request.
- Infrastructure failures nack with `requeue=False`.
- Initial connection failures use exponential backoff; `aio-pika`
  `RobustConnection` handles reconnects after the first connection.

## Integration audit

Audit is always available to handlers; there is no enable/disable env flag.
Call it explicitly around each external request:

```python
import time

started = time.monotonic()
log_id = await audit_repository.create_pending_log(
    message_type,
    message,
    device_id,
    request_id,
    "GET",
    request_url,
    None,
)
success, data, headers, status_code, error = await context.get(path)
duration_ms = int((time.monotonic() - started) * 1000)
await audit_repository.complete_log(
    log_id, status_code, data, headers, duration_ms
)
```

The repository:

- connects lazily on the first audit call;
- skips logging when `request_id` is missing;
- logs and swallows database failures so service processing continues;
- retries on a later audit call after `DB_RECONNECT_INTERVAL`;
- writes `SERVICE_TYPE` and stamps `SERVICE_USER_ID`;
- resolves `terminal.device_id` to `terminal.id`;
- updates the exact row ID returned by `create_pending_log`.

Odoo owns the `integration_request_response` and `terminal` tables and all
schema migrations. The framework never creates or migrates them.

## HTTP and lifecycle

- `GET /health`: service and RabbitMQ state (`ok` or `degraded`).
- `GET /`: service name.
- `POST /debug/simulate-request`: same routing path as RabbitMQ, registered only
  when `APP_ENV=development`.

Optional extension points:

```python
IntegrationService(
    ...,
    extra_tasks=[my_poller],           # async (settings, context) -> None
    configure_app=mount_routes,        # (app: FastAPI) -> None
    on_shutdown=[client.close],        # async cleanup hooks
)
```

HTTP/SOAP/gRPC clients remain service-specific.

## Common environment contract

Every service should copy all variables from [.env.example](.env.example)
unchanged and append only service-specific variables.

| Variable | Default |
|---|---|
| `SERVICE_NAME` | `Integration Service` |
| `SERVICE_TYPE` | required |
| `RABBITMQ_HOST` / `RABBITMQ_PORT` | `localhost` / `5672` |
| `RABBITMQ_USER` or `RABBITMQ_USERNAME` | `guest` |
| `RABBITMQ_PASSWORD` / `RABBITMQ_VHOST` | `guest` / `/` |
| `RABBITMQ_REQUEST_TOPIC` | `requests` |
| `RABBITMQ_REQUEST_QUEUE` | required |
| `RABBITMQ_RESPONSE_TOPIC` | `responses` |
| `CONSUMER_PREFETCH_COUNT` | `10` |
| `RABBITMQ_HEARTBEAT` / `RABBITMQ_CONNECTION_TIMEOUT` | `600` / `10` |
| `RABBITMQ_MAX_RETRY_ATTEMPTS` | `0` (forever) |
| `RABBITMQ_INITIAL_RETRY_DELAY` / `RABBITMQ_MAX_RETRY_DELAY` | `1` / `60` |
| `RABBITMQ_RETRY_BACKOFF_MULTIPLIER` | `2` |
| `HTTP_PORT` | `8080` |
| `LOG_LEVEL` / `LOG_FILE` / `LOG_RETENTION_DAYS` | `INFO` / empty / `7` |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | empty |
| `DB_POOL_MAX` / `DB_CONNECT_TIMEOUT` | `15` / `5` |
| `DB_STATEMENT_TIMEOUT_MS` / `DB_RECONNECT_INTERVAL` | `5000` / `60` |
| `SERVICE_USER_ID` | `1` |
| `APP_ENV` | empty |

Services subclass `FrameworkSettings` and add fields such as
`betbox_api_base_url`; common settings keep the same names everywhere.

## Consumer migration checklist

1. Require Python 3.11+ and pin a released framework tag.
2. Subclass `FrameworkSettings`; set `service_type` and request queue.
3. Keep the external client in the consumer and pass it as `context`.
4. Adapt handlers to the six-argument contract and standard return tuple.
5. Use the framework audit repository and its returned row ID.
6. Build `IntegrationService`; register client cleanup in `on_shutdown`.
7. Remove local RabbitMQ, FastAPI health/debug, logging, lifecycle, and audit code.
8. Copy the common env contract and append service-specific variables.
9. Install `git` in Docker's builder stage.
10. Run lint, unit tests, and a debug/RabbitMQ smoke test.

## Codex skill

The repository includes
[`build-integration-service`](skills/build-integration-service/SKILL.md), which
guides Codex through creating or migrating consumer services with this
ownership boundary. Keep it versioned with the framework. Copy or link its
folder into `$CODEX_HOME/skills` when it should be globally discoverable.

## Development and release

```bash
pip install -e .[dev]
ruff check .
pytest
```

For a local smoke test, start `docker-compose.rabbitmq.yml`, run the echo
example, and call its development debug endpoint.

To release:

1. Bump `version` in `pyproject.toml`.
2. Commit and push the change.
3. Create and push `vX.Y.Z`.
4. Update consumer `requirements.txt` files to that tag.
