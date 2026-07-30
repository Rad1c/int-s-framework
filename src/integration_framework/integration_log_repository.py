"""Best-effort PostgreSQL audit logging for integration requests."""

import asyncio
import json
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

import psycopg2
import psycopg2.pool
from cachetools import TTLCache

from integration_framework.settings import FrameworkSettings

_logger = logging.getLogger(__name__)


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


class IntegrationLogRepository:
    """Writes integration_request_response records without affecting service flow."""

    def __init__(self, settings: FrameworkSettings, logger: logging.Logger | None = None):
        self.settings = settings
        self.logger = logger or _logger
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None
        self._next_connect_attempt = 0.0
        self._closed = False
        self._pool_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._terminal_pk_cache: TTLCache = TTLCache(maxsize=1000, ttl=3600)

    def close(self) -> None:
        with self._pool_lock:
            self._closed = True
            pool, self._pool = self._pool, None
        if pool:
            try:
                pool.closeall()
            except Exception:
                self.logger.exception("Failed to close integration log connection pool")

    async def create_pending_log(
        self,
        message_type: str | None,
        message: Any,
        device_id: str | None,
        request_id: str | None,
        http_method: str | None,
        request_url: str,
        request_body: Any,
    ) -> int | None:
        if not request_id:
            self.logger.warning(
                "Skipping integration request log: no X-Request-Id provided (url=%s)",
                request_url,
            )
            return None
        return await asyncio.to_thread(
            self._create_pending_log_sync,
            message_type,
            message,
            device_id,
            request_id,
            http_method,
            request_url,
            request_body,
        )

    async def complete_log(
        self,
        log_id: int | None,
        status_code: int | None,
        response_body: Any,
        response_headers: Any,
        duration_ms: int | None,
    ) -> None:
        if log_id is None:
            return
        await asyncio.to_thread(
            self._complete_log_sync,
            log_id,
            status_code,
            response_body,
            response_headers,
            duration_ms,
        )

    def _ensure_pool(self) -> psycopg2.pool.ThreadedConnectionPool | None:
        if self._pool or self._closed or time.monotonic() < self._next_connect_attempt:
            return self._pool

        with self._pool_lock:
            if self._pool or self._closed or time.monotonic() < self._next_connect_attempt:
                return self._pool
            try:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=self.settings.db_pool_max,
                    host=self.settings.postgres_host,
                    port=self.settings.postgres_port,
                    dbname=self.settings.postgres_db,
                    user=self.settings.postgres_user,
                    password=self.settings.postgres_password,
                    connect_timeout=self.settings.db_connect_timeout,
                    options=f"-c statement_timeout={self.settings.db_statement_timeout_ms}",
                )
                self.logger.info(
                    "Integration log connection pool initialized (min=1, max=%d)",
                    self.settings.db_pool_max,
                )
            except Exception:
                self._next_connect_attempt = time.monotonic() + self.settings.db_reconnect_interval
                self.logger.exception(
                    "Integration log database unavailable; retrying in %ss",
                    self.settings.db_reconnect_interval,
                )
            return self._pool

    def _reset_pool(self, pool: psycopg2.pool.ThreadedConnectionPool) -> None:
        with self._pool_lock:
            if self._pool is not pool:
                return
            self._pool = None
            self._next_connect_attempt = time.monotonic() + self.settings.db_reconnect_interval
        # ponytail: audit writes may race with pool reset; failures are swallowed by design.
        try:
            pool.closeall()
        except Exception:
            self.logger.exception("Failed to close unavailable integration log connection pool")

    def _release_connection(
        self,
        pool: psycopg2.pool.ThreadedConnectionPool,
        connection,
        reset_pool: bool,
    ) -> None:
        if reset_pool:
            self._reset_pool(pool)
            return
        if connection:
            try:
                pool.putconn(connection)
            except Exception:
                self.logger.exception("Failed to return integration log database connection")
                self._reset_pool(pool)

    def _resolve_terminal_pk(self, cursor, device_id: str | None) -> int | None:
        if not device_id:
            return None

        with self._cache_lock:
            if device_id in self._terminal_pk_cache:
                return self._terminal_pk_cache[device_id]

        cursor.execute("SELECT id FROM terminal WHERE device_id = %s LIMIT 1", (device_id,))
        row = cursor.fetchone()
        if not row:
            return None

        terminal_id = row[0]
        with self._cache_lock:
            self._terminal_pk_cache[device_id] = terminal_id
        return terminal_id

    def _create_pending_log_sync(
        self,
        message_type,
        message,
        device_id,
        request_id,
        http_method,
        request_url,
        request_body,
    ) -> int | None:
        pool = self._ensure_pool()
        if pool is None:
            return None

        connection = None
        reset_pool = False
        try:
            connection = pool.getconn()
            connection.autocommit = False
            cursor = connection.cursor()
            terminal_id = self._resolve_terminal_pk(cursor, device_id)
            now = datetime.now(UTC)
            cursor.execute(
                """
                INSERT INTO integration_request_response
                    (terminal_id, service_type, message_type, message, request_id, http_method,
                     request_url, request, occurred_at, create_date, write_date, create_uid, write_uid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    terminal_id,
                    self.settings.service_type,
                    message_type,
                    _dump(message),
                    request_id,
                    http_method,
                    request_url,
                    _dump(request_body),
                    now,
                    now,
                    now,
                    self.settings.service_user_id,
                    self.settings.service_user_id,
                ),
            )
            log_id = cursor.fetchone()[0]
            connection.commit()
            return log_id
        except Exception as error:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    reset_pool = True
            reset_pool = reset_pool or isinstance(
                error, (psycopg2.InterfaceError, psycopg2.OperationalError)
            )
            self.logger.exception("Failed to write pending integration request log")
            return None
        finally:
            self._release_connection(pool, connection, reset_pool)

    def _complete_log_sync(
        self,
        log_id,
        status_code,
        response_body,
        response_headers,
        duration_ms,
    ) -> None:
        pool = self._ensure_pool()
        if pool is None:
            return

        connection = None
        reset_pool = False
        try:
            connection = pool.getconn()
            connection.autocommit = False
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE integration_request_response
                SET status_code = %s,
                    response = %s,
                    response_headers = %s,
                    duration_ms = %s,
                    is_error = %s,
                    write_date = %s,
                    write_uid = %s
                WHERE id = %s
                """,
                (
                    status_code,
                    _dump(response_body),
                    _dump(response_headers),
                    duration_ms,
                    status_code is None or status_code >= 400,
                    datetime.now(UTC),
                    self.settings.service_user_id,
                    log_id,
                ),
            )
            connection.commit()
        except Exception as error:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    reset_pool = True
            reset_pool = reset_pool or isinstance(
                error, (psycopg2.InterfaceError, psycopg2.OperationalError)
            )
            self.logger.exception("Failed to complete integration request log")
        finally:
            self._release_connection(pool, connection, reset_pool)
