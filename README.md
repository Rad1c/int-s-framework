# integration-service-framework

Shared foundation for Monroe integration services (betbox, internal backoffice, ...).
Packages the RabbitMQ request/response pipeline, handler routing, health/debug
endpoints, configuration, logging, and service lifecycle — so a concrete
integration service only writes **handlers**.

## Installation

Pin a git tag in `requirements.txt`:

```
integration-service-framework @ git+https://github.com/monroe-solutions/integration-service-framework@v0.1.0
```

For private repos, CI/Docker builds need a token, e.g.:

```
git+https://${GITHUB_TOKEN}@github.com/monroe-solutions/integration-service-framework@v0.1.0
```

## Quick start

A complete service is three pieces — settings, handlers, and a `main`:

```python
from integration_framework import FrameworkSettings, HandlerRegistry, IntegrationService

registry = HandlerRegistry()


class Settings(FrameworkSettings):
    service_name: str = "Betbox Integration Service"
    service_type: str = "betbox_service"          # serviceType this instance handles
    rabbitmq_request_queue: str = "requests.betbox"  # per-service queue


@registry.handler("RedeemTicket")
async def handle_redeem_ticket(
    payload, context, logger, device_id, request_id, audit_repository
):
    message = payload.get("message") or {}
    success, data, headers, error = await context.get(f"/api/CashReceipt/info/{message['barcode']}")
    return success, {"data": data, "headers": headers}, error


def main():
    settings = Settings()
    api_client = ...  # service-specific HTTP/SOAP/gRPC client
    service = IntegrationService(
        settings=settings,
        registry=registry,
        context=api_client,               # passed to every handler
        on_shutdown=[api_client.close],
    )
    service.run()


if __name__ == "__main__":
    main()
```

A runnable minimal example lives in [examples/echo_service](examples/echo_service/main.py).

## What the framework does

### Messaging pipeline

- Requests are fanned out from a shared **fanout exchange** (`requests`) to a
  durable **per-service queue** (`requests.<service>`), so every integration
  service receives its own copy of each request.
- Messages are dispatched by `serviceType` (mismatch → acked, no response) and
  `payload.messageType` (handler lookup in the `HandlerRegistry`).
- The handler result `(success: bool, payload: dict, error_message: str)` is
  wrapped in the standard response envelope and published to the `responses`
  queue with the inbound message's `X-Device-Id` / `X-Request-Id` headers:

  ```json
  {"success": 0, "payload": {...}, "error_message": ""}
  ```

  `success`: `0` = OK, `1` = error.
- Invalid JSON and handler errors produce an error envelope and the message is
  acked; infrastructure failures nack (`requeue=False`).
- Initial connection retries with exponential backoff; after connecting,
  aio-pika's `RobustConnection` handles reconnects automatically.

### HTTP endpoints

- `GET /health` — `ok`/`degraded` + RabbitMQ connection state.
- `GET /` — service name banner.
- `POST /debug/simulate-request` — **development only** (`APP_ENV=development`):
  runs a request through the exact same processing path as a RabbitMQ message
  and returns the envelope directly.

### Extension points

For service-specific consumers/pollers and routes:

```python
IntegrationService(
    ...,
    extra_tasks=[my_poller],           # async (settings, context) -> None; cancelled on shutdown
    configure_app=mount_extra_routes,  # (app: FastAPI) -> None
    on_shutdown=[cleanup],             # async hooks run after tasks stop
)
```

`integration_framework.create_robust_connection(settings, state, logger, name)`
builds a state-tracked robust connection for custom consumers.
HTTP/SOAP/gRPC clients stay service-specific and are passed through `context`.

### Integration audit

Every handler receives the framework-owned `audit_repository` as its last
argument. The repository opens its PostgreSQL pool lazily, never interrupts
message processing on database failures, and retries after
`DB_RECONNECT_INTERVAL`:

```python
log_id = await audit_repository.create_pending_log(
    message_type, message, device_id, request_id, "GET", request_url, None
)
result = await context.get(path)
await audit_repository.complete_log(
    log_id, result.status_code, result.data, result.headers, duration_ms
)
```

Missing `request_id` or a failed database write makes the audit call a no-op.
The Odoo application owns the `integration_request_response` and `terminal`
tables and their migrations.

## Configuration (environment variables / `.env`)

| Variable | Default | Description |
|---|---|---|
| `SERVICE_NAME` | `Integration Service` | Display name (FastAPI title, health banner) |
| `SERVICE_TYPE` | **required** | `serviceType` this instance handles |
| `RABBITMQ_HOST` / `RABBITMQ_PORT` | `localhost` / `5672` | Broker address |
| `RABBITMQ_USER` (alias `RABBITMQ_USERNAME`) | `guest` | Broker credentials |
| `RABBITMQ_PASSWORD` | `guest` | |
| `RABBITMQ_VHOST` | `/` | |
| `RABBITMQ_REQUEST_TOPIC` | `requests` | Fanout exchange for inbound requests |
| `RABBITMQ_REQUEST_QUEUE` | **required** | Per-service queue, e.g. `requests.betbox` |
| `RABBITMQ_RESPONSE_TOPIC` | `responses` | Queue for response envelopes |
| `CONSUMER_PREFETCH_COUNT` | `10` | Channel QoS |
| `RABBITMQ_HEARTBEAT` | `600` | AMQP heartbeat (s) |
| `RABBITMQ_CONNECTION_TIMEOUT` | `10` | Connect timeout (s) |
| `RABBITMQ_MAX_RETRY_ATTEMPTS` | `0` (forever) | Initial-connect retries |
| `RABBITMQ_INITIAL_RETRY_DELAY` / `RABBITMQ_MAX_RETRY_DELAY` | `1` / `60` | Backoff bounds (s) |
| `RABBITMQ_RETRY_BACKOFF_MULTIPLIER` | `2` | |
| `HTTP_PORT` | `8080` | Uvicorn port |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FILE` | *(empty — console only)* | Enables daily-rotating file log |
| `LOG_RETENTION_DAYS` | `7` | Rotated file retention |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` | Integration audit database |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | *(empty)* | Integration audit credentials |
| `DB_POOL_MAX` | `15` | Maximum audit database pool size |
| `DB_CONNECT_TIMEOUT` | `5` | Audit database connect timeout (s) |
| `DB_STATEMENT_TIMEOUT_MS` | `5000` | Audit SQL statement timeout |
| `DB_RECONNECT_INTERVAL` | `60` | Cooldown before lazy reconnect (s) |
| `SERVICE_USER_ID` | `1` | Odoo audit user ID |
| `APP_ENV` | *(empty)* | `development` enables `/debug` routes |

Services subclass `FrameworkSettings` (pydantic-settings) and add their own fields.

## Development

```
pip install -e .[dev]
ruff check .
pytest
```

Local end-to-end smoke test: `docker compose -f docker-compose.rabbitmq.yml up -d`,
then run `examples/echo_service/main.py` (see instructions in that file).

## Releasing

1. Bump `version` in `pyproject.toml`.
2. Tag: `git tag v0.x.y && git push --tags`.
3. Consumers update the tag in their `requirements.txt`.
