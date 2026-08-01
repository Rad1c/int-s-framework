# Integration audit

Verified facts about `IntegrationLogRepository` —
[integration_log_repository.py](../../src/integration_framework/integration_log_repository.py).

## Ownership

Odoo owns the `integration_request_response` and `terminal` tables and every migration to them. The
framework only inserts and updates rows. It writes the Odoo bookkeeping columns itself:
`create_date`, `write_date`, `create_uid`, `write_uid`, the last two from `SERVICE_USER_ID`.

## Best-effort by design

Audit is always constructed and always passed to handlers; there is intentionally **no enable
flag**. Every failure path logs and swallows, so a missing database degrades audit only, never
message processing. Two consequences that look like bugs but are not:

- `create_pending_log` returns `None` when `X-Request-Id` is missing or the write failed;
  `complete_log` is then a no-op on that `None`.
- The pool opens **lazily on the first audit call**. A service can start and process messages with
  PostgreSQL down. After a failure, reconnection is not attempted until `DB_RECONNECT_INTERVAL`
  seconds have passed, and only on the next audit call — there is no background retry.

## Two-phase call, owned by the handler

The handler calls `create_pending_log` before the external request and `complete_log` after it,
passing back the returned row ID. Duration is measured in the handler because the handler owns the
client call. The framework cannot do this itself without knowing the protocol.

`is_error` is derived on completion: `status_code is None or status_code >= 400`.

## Threading

`psycopg2` is synchronous, so both operations run through `asyncio.to_thread` off the event loop
onto a `ThreadedConnectionPool` (`min=1`, `max=DB_POOL_MAX`). `statement_timeout` is set per
connection from `DB_STATEMENT_TIMEOUT_MS`. The pool and the terminal cache each have their own lock.

On `InterfaceError` / `OperationalError`, or when a rollback itself fails with `psycopg2.Error`, the
whole pool is dropped and rebuilt after `DB_RECONNECT_INTERVAL` — a stale pool after a database
restart poisons every later connection, so it is discarded rather than reused.

## Terminal resolution

`X-Device-Id` is a device identifier, not the `terminal` primary key. `_resolve_terminal_pk` looks
it up and caches the result in a `TTLCache` (1000 entries, 1 hour). An unknown device resolves to
`NULL` `terminal_id` and is **not** cached, so a terminal created later is picked up on the next
request.
