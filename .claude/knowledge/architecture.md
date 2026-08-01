# Architecture

Verified facts about how the framework processes a request. Source files are linked instead of
restated — read them when the detail matters.

## Ownership boundary

The framework is infrastructure only. It never knows the protocol, endpoints, or payload shapes of
the system a service integrates with. A consumer service supplies three things: a
`FrameworkSettings` subclass, a `HandlerRegistry`, and a `context` object (usually its API client).
The full table is in the repository `README.md`.

## Request lifecycle

1. Requests are published to a **durable fanout exchange** (`RABBITMQ_REQUEST_TOPIC`, default
   `requests`). Every service binds its own durable queue (`RABBITMQ_REQUEST_QUEUE`) to it, so
   **every service receives a copy of every request** —
   [request_consumer.py](../../src/integration_framework/messaging/request_consumer.py).
2. `route_payload` compares the message's `serviceType` against `settings.service_type`. A mismatch
   returns `None`, and the consumer acks **without publishing a response** — this is the normal path
   for the copies fanned out to other services, not an error.
3. A matching message dispatches on `payload.messageType` through the `HandlerRegistry`.
4. The handler result `(success, payload, error_message)` is wrapped by `envelope()` and published
   to the response queue (`RABBITMQ_RESPONSE_TOPIC`, default `responses`) via the **default
   exchange**, keyed by queue name. The consumer declares that queue at startup so publishes are
   not silently dropped.
5. `X-Device-Id` and `X-Request-Id` are read from the inbound headers and echoed onto the response —
   [publisher.py](../../src/integration_framework/messaging/publisher.py). They are the only
   correlation identifiers the pipeline carries; both are optional and may be `None`.

## Ack semantics

| Situation | Response published | Message |
|---|---|---|
| Invalid JSON | error envelope | ack |
| `serviceType` mismatch | none | ack |
| Unknown `messageType` | error envelope | ack |
| Handler raises | error envelope | ack |
| Failure outside handling (publish, ack, decode) | none | nack, `requeue=False` |

Handler exceptions are caught in `route_payload` and converted to an error envelope; only
infrastructure failures reach the `_on_request` except block that nacks. Nothing is ever requeued,
so there is no poison-message loop and no dead-letter configuration.

## Connection and reconnect

Two layers, and they are easy to confuse:

- The **outer loop** in `RequestConsumer.run` handles *initial* connection failures with exponential
  backoff (`RABBITMQ_INITIAL_RETRY_DELAY` → `RABBITMQ_MAX_RETRY_DELAY`, multiplier, `0` attempts =
  forever).
- After the first successful connect, **aio-pika's `RobustConnection` owns reconnection**; it
  re-declares and re-registers consumers itself.
  [connection.py](../../src/integration_framework/messaging/connection.py) only wires
  reconnect/close callbacks into `ConsumerState`.

`_connect_and_consume` parks on `await asyncio.Future()` — it returns only when cancelled.

## Process shape

`IntegrationService` builds a FastAPI app and runs uvicorn as the **blocking foreground process**;
the consumer and any `extra_tasks` are asyncio tasks started by the FastAPI lifespan, so SIGINT and
SIGTERM cancel them, then `on_shutdown` hooks run, then the audit pool closes —
[app.py](../../src/integration_framework/app.py).

`GET /health` reports `ok` or `degraded` from `ConsumerState`; the process stays alive and the HTTP
port stays open while RabbitMQ is down.

`POST /debug/simulate-request` is registered only when `APP_ENV=development` and calls
`RequestConsumer.process` — the same routing path as a real message, with the envelope returned in
the HTTP response instead of published. It is the reason a smoke test does not need a broker.

## Settings

`FrameworkSettings` is a pydantic-settings `BaseSettings` with `extra: ignore`, which is what lets a
consumer keep its own variables in the same `.env`. `service_type` and `rabbitmq_request_queue` have
no defaults — constructing settings without them raises `ValidationError`.
