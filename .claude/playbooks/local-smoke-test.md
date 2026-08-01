# Local Smoke Test

Use this playbook to exercise a framework change end to end, beyond the unit suite. The echo
example is a real service built on the framework and needs no external system to be useful.

## Without a broker — routing, handlers, envelopes, audit

The development debug endpoint runs the exact path a RabbitMQ message takes, so most changes can be
verified with no infrastructure at all.

1. `pip install -e .[dev]`
2. Start the example with `APP_ENV=development` set:
   `python examples/echo_service/main.py`. It logs a connection failure and retries — expected, and
   proof that the HTTP surface survives a broken broker.
3. Check `GET /health` reports `degraded` with a `last_error`, and `GET /` returns the service name.
4. Post a request through the same routing path:

   ```bash
   curl -X POST http://localhost:8080/debug/simulate-request \
     -H "Content-Type: application/json" \
     -H "X-Device-Id: dev-1" -H "X-Request-Id: req-1" \
     -d '{"serviceType": "echo_service", "payload": {"messageType": "Echo", "message": {"text": "hello"}}}'
   ```

5. Confirm the envelope: `success` is `0`, the correlation headers are echoed back. Then confirm
   the negative paths — a foreign `serviceType` returns `{"ignored": true}`, an unknown
   `messageType` returns `success: 1` with the error message.

## With a broker — connection, consume, ack, publish

Needed for any change to the consumer, connection, or publisher.

1. `docker compose -f docker-compose.rabbitmq.yml up -d`
2. Start the example service and confirm `/health` flips to `ok`.
3. Publish the same JSON to the `requests` exchange from the management UI
   (http://localhost:15672, guest/guest), with `X-Device-Id` and `X-Request-Id` headers set.
4. Confirm the response envelope arrives on the `responses` queue carrying both headers, and that
   the request queue drains.
5. To exercise reconnect, stop and restart the broker container: `/health` goes `degraded` then
   returns to `ok` without restarting the service, and a message published after the restart is
   still consumed.
6. Tear down with `docker compose -f docker-compose.rabbitmq.yml down`.

Audit writes need a PostgreSQL instance holding the Odoo-owned `integration_request_response` and
`terminal` tables; the framework never creates them. Without one, audit calls log a connection
failure and processing continues — that is the designed behavior, not a failed smoke test.
