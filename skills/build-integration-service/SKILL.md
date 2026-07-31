---
name: build-integration-service
description: Build or migrate Python integration services onto integration-service-framework. Use when creating a new RabbitMQ integration service, adding service-specific handlers or clients, replacing duplicated RabbitMQ/FastAPI/logging/audit infrastructure, standardizing environment variables, or wiring a consumer repository to a released framework tag.
---

# Build Integration Service

Use the framework as infrastructure and keep business-specific behavior in the
consumer repository.

## Inspect first

1. Read the framework `README.md`, `.env.example`, public exports, settings,
   handler router, lifecycle, and audit repository.
2. Read the consumer entry point, configuration, handlers, external clients,
   tests, Dockerfile, Compose files, and CI workflow.
3. Find duplicated RabbitMQ, health/debug, logging, lifecycle, and database
   repository code before editing.
4. Preserve service-specific protocol clients, business transformations,
   certificates, and endpoints.

## Apply the ownership boundary

Make the framework own:

- RabbitMQ connect, consume, publish, ack/nack, and reconnect;
- routing, response envelopes, and correlation headers;
- FastAPI lifecycle, health, and development debug routes;
- common settings and logging;
- the lazy best-effort integration audit repository.

Make the consumer own:

- its external HTTP/SOAP/gRPC client;
- service-specific settings;
- business handlers and endpoint paths;
- explicit audit calls around external requests.

Delete consumer implementations replaced by the framework and delete their
tests. Do not retain compatibility wrappers for dead internal APIs.

## Wire the consumer

1. Pin a released framework tag in `requirements.txt`.
2. Require Python 3.11+.
3. Subclass `FrameworkSettings`, set `service_name`, `service_type`, and
   `rabbitmq_request_queue`, then add only service-specific fields.
4. Register handlers through `HandlerRegistry`.
5. Pass the service client as `IntegrationService.context`.
6. Register async client cleanup through `on_shutdown`.

Use the exact handler contract:

```python
async def handler(
    payload, context, logger, device_id, request_id, audit_repository
) -> tuple[bool, dict, str]:
    ...
```

Return business success as a boolean. Do not build the numeric response
envelope in the consumer.

## Add audit calls

Call `create_pending_log` immediately before the external operation. Measure
duration in the handler because the service owns the client call. Pass the
returned row ID to `complete_log`.

Do not add an audit enable flag. Treat a missing request ID or unavailable
database as a best-effort no-op. Never let audit failure interrupt business
processing.

Keep all common database variables in the consumer env template. Let Odoo own
the `integration_request_response` and `terminal` schemas and migrations.

## Align delivery files

- Copy all common variables from `.env.example`; append only service variables.
- Install `git` in the Docker builder stage for the VCS dependency.
- Remove direct dependencies now supplied transitively and no longer imported.
- Run CI only on Python versions supported by the framework.
- Keep Ruff blocking rather than masking failures.

## Verify

1. Install the consumer from its normal requirements files so the Git tag is tested.
2. Run Ruff on source and tests.
3. Run the full unit suite.
4. Instantiate settings and a registry to verify framework wiring without
   connecting to RabbitMQ or PostgreSQL.
5. Validate Docker Compose.
6. Build the Docker image when a Docker engine is available.

Use `../../README.md` for the current API contract and
`../../examples/echo_service/main.py` for minimal wiring.
